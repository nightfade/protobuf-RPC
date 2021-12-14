tags: 
- protobuf
- RPC
- Network
comments: true
date: 2013-12-15 11:12:41 +0800
layout: post
status: public
title: 'Implement an Asynchronous RPC Basing on Protocol Buffers'
---

在前一篇博文《Dive Into Protocol Buffers Python API》中对*protobuf*的Python API的代码进行了分析。现在进入实践阶段，利用*protobuf*的`service` API实现一套异步RPC机制。

严谨起见，从*wikipedia*上摘录下一般情况下一次RPC调用的过程：

>1. The client calls the client stub. The call is a **local procedure call**, with parameters pushed on to the stack in the normal way.
>2. The client stub packs the parameters into a message and makes a system call to send the message. Packing the parameters is called **marshalling**.
>3. The client's local operating system **sends** the message from the client machine to the server machine.
>4. The local operating system on the server machine passes the **incoming** packets to the server stub.
>5. The server stub unpacks the parameters from the message. Unpacking the parameters is called **unmarshalling**.
>6. Finally, the server stub calls **the server procedure**. The reply traces the same steps in the reverse direction.

上面过程中的第1和第6步已经由*protobuf*的`service` API为我们实现好了，我们只需要在proto文件中定义所需的具体调用接口即可。

对于第2和第5步的*marshalling*和*unmarshalling*步骤，`service` API虽然没有为我们完全实现，但是*protobuf*为方法以及参数已经准备好了完善的*serialization*的机制，我们只需要自己决定如何用这些序列化的数据拼装数据包即可。

最后，第3和第4步的通信机制则是完全需要由我们自己来实现的，这也是*protobuf*设计的初衷，在最多变的部分（多种多样的网络结构、协议和通信机制）留出足够的空间让程序员可以针对特定场景自己实现，使得*protobuf*可以应用在更多的场景。

回到标题所说的*Asynchronous RPC*。一次函数调用通常包含了输入和输出两个过程。对于RPC来说，我们可以像大多数本地函数那样，在进行调用之后一直等待，直到计算结果返回才继续向下执行。但是由于网络传输的过程相对比较耗时，采取这样的策略无疑是非常低效的。因此我们采取另外一种策略：调用者发送调用请求之后不等待结果的返回就立即继续执行后续的操作，当收到RPC返回的计算结果之后再回来处理。这里将前一种策略称为*Synchronous RPC*，而后一种就是本文要实现的*Asynchronous RPC*。

实现的方式其实也很简单，就是把客户端发起的一次RPC调用拆分成两次来处理：首先由客户端发起RPC调用，之后无需等待继续向后执行；而服务端接收到RPC调用请求并处理完成之后，再向客户端发起另外一次RPC调用，将计算结果通过参数通知客户端。

关于RPC需要说明的东西大概就到这里，接下来我们首先解决第3和第4步的通信机制的实现。

## 实现通信层

我们选择使用asyncore和TCP协议实现RPC的通信层。关于asyncore的具体用法可以参考[asyncore的文档](http://docs.python.org/2/library/asyncore.html)。

首先将端到端的链接和传输抽象出来，一个端到端的通信可以用下面这样一个`TcpConnection`来进行封装：

```python
class TcpConnection(asyncore.dispatcher):

    ST_INIT = 0
    ST_ESTABLISHED = 1
    ST_DISCONNECTED = 2

    def __init__(self, sock):
        asyncore.dispatcher.__init__(self, sock)
        self.peername = peername
        self.writebuff = ''
        self.status = TcpConnection.ST_ESTABLISHED if sock else TcpConnection.ST_INIT

    def handle_read(self):
        data = self.recv(4096)
        # process data here

    def handle_write(self):
        if self.writebuff:
            size = self.send(self.writebuff)
            self.writebuff = self.writebuff[size:]

    def writable(self):
        if self.status == TcpConnection.ST_ESTABLISHED:
            return len(self.writebuff) > 0
        else:
            return True

    def send_data(self, data):
        self.writebuff += data
```

客户端负责主动向服务端发起连接请求，在请求成功后维护自己到服务端的**一条**连接。因此我们可以通过继承`TcpConnection`并增加`connect`行为得到通信的客户端：

```python
class TcpClient(TcpConnection):

    def __init__(self, ip, port):
        TcpConnection.__init__(self, None)
        self.ip = ip
        self.port = port

    def async_connect(self):
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connect(self.peername)

    def handle_connect(self):
        self.status = TcpConnection.ST_ESTABLISHED
```


服务端则负责监听并接受客户端的连接请求，并为每一个客户维护一条连接：

```python
class TcpServer(asyncore.dispatcher):

    def __init__(self, ip, port):
        asyncore.dispatcher.__init__(self)
        self.ip = ip
        self.port = port

        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.bind((self.ip, self.port))
        self.listen(10)

    def handle_accept(self):
        try:
            sock, addr = self.accept()
        except socket.error, e:
            self.logger.warning('accept error: ' + e.message)
            return
        except TypeError, e:
            self.logger.warning('accept error: ' + e.message)
            return

        conn = TcpConnection(sock, addr)
        self.handle_new_connection(conn)

    def handle_new_connection(self, conn):
    	""" handle new connection here """
    	pass
```

至此，我们就完成了一个简陋但有效的C/S模式的通信层。

## 实现Echo服务

有了通信层，我们就可以继续向下进行。既然是RPC，那么就不可能脱离具体的业务，因此这里以经典的*Echo*服务为例，利用*protobuf*实现RPC。

我们为Echo定义proto如下：

```protobuf
package nightfade;

option py_generic_services = true;

message Void {}

message EchoString {
    required string message = 1;
}

service IEchoService {
    rpc echo(EchoString) returns(Void);
}

service IEchoClient {
    rpc respond(EchoString) returns(Void);
}

```

如前所述，因为要实现的是*Asynchronous RPC*，所以RPC调用分为两部分：

客户端首先调用`echo`，之后服务端接收到RPC请求并处理之后再调用`respond`将结果通知客户端。

使用*protoc*编译proto文件以及对生成的文件的分析这里就不在赘述，可以参考《Dive Into Protocol Buffers Python API》。这里需要关注的问题有两个：

1. 如何实现*Service*。
2. 如何将实现好的*Service*与我们的通信层关联起来。

因为Echo服务本身非常简单，所以第一个问题可以轻易解决：

```python
class EchoService(IEchoService):
    def echo(self, rpc_controller, echo_string, callback=None):
        client_stub = IEchoClient_Stub(rpc_controller.rpc_channel)
        client_stub.respond(rpc_controller, echo_string, callback=None)
```

接下来我们需要考虑的就是与通信层的关联问题。

要将*protobuf*的`service`与通信层关联的关键在于`RpcChannel`。

首先来看调用端这一边。

调用端通过*stub*对RPC过程的调用最终会转向对`RpcChannel.CallMethod()`的调用，而这个方法也正是*protobuf*留给我们实现调用端进行**marshalling**和数据发送的地方。这样一来问题就很容易解决了，我们为RpcChannel实现`CallMethod`方法：

1. 无论是调用端还是被调用端，一个`method_descriptor`在其所在*Service*内的*index*是一致的。因此*method_descriptor*的部分只需要对其*index*进行*marshalling*即可。
2. RPC调用的参数可以直接使用*protobuf*的`SerializeToString()`方法进行*marshalling*，进而在接收端通过`ParseFromString()`方法*unmarshalling*。
3. 数据包的*Framing*问题，则使用一个简单的方案：在数据包之前发送一个32位整数的*HEAD*用来告知接收端后续数据包的大小。

具体实现来看代码：

```python
class RpcChannel(service.RpcChannel):

    HEAD_FMT = '!I'
    INDEX_FMT = '!H'
    HEAD_LEN = struct.calcsize(HEAD_FMT)
    INDEX_LEN = struct.calcsize(INDEX_FMT)

    def __init__(self, conn):
        super(RpcChannel, self).__init__()
        self.conn = conn

    def CallMethod(self,
                   method_descriptor,
                   rpc_controller,
                   request,
                   response_class,
                   done):
        index = method_descriptor.index
        data = request.SerializeToString()
        size = RpcChannel.INDEX_LEN + len(data)

        self.conn.send_data(struct.pack(RpcChannel.HEAD_FMT, size))
        self.conn.send_data(struct.pack(RpcChannel.INDEX_FMT, index))
        self.conn.send_data(data)
```


接下来实现被调用端。

*protobuf*的`service` API在被调用端为我们完成的工作是，当使用合适的`method_descriptor`和`request`参数调用`IEchoService.CallMethod()`时，会自动调用我们对相应方法接口的具体实现。因此在服务端需要做的工作主要由：

1. 接受调用端发来的数据。
2. 对接收到的数据包进行*unmashalling*，解析得到`method_descriptor`和`request`参数。
3. 调用`EchoService.CallMethod()`。

我们实现的`TcpConnection`可以完成接受数据的工作，只是还没能与后续的步骤关联起来。既然*marshalling*的工作是由`RpcChannel`来完成的，*unmarshalling*的功能我们也同样在`RpcChannel`中实现，为其增加`receive`方法。当`TcpConnection`接受到数据之后，就交给`RpcChannel.receive`进行处理。

```python
    def receive(self, data):
        try:
            rpc_calls = self.rpc_parser.feed(data)
        except (AttributeError, IndexError), e:
            self.close()
            return

        for method_descriptor, request in rpc_calls:
            self.service_local.CallMethod(method_descriptor, self.rpc_controller, request, callback=None)
```

其中`rpc_parser`负责将数据流*unmarshalling*成一系列的`method_descriptor`和`request`参数，具体实现就不再贴代码了。`service_local`则是服务端提供的服务`EchoService`。

至此，我们的整个RPC调用的的基本实现就已经完成了！限于篇幅，所以只贴了一些代码片段，完整的代码可以查看我的repository：<https://github.com/nightfade/protobuf-RPC>。

## 其他

在这个RPC的实现中，其实还欠缺了一个重要部分`RpcController`。这个部分是干什么用的呢？依然引用*wikipedia*的一段说明：

>An important difference between remote procedure calls and local calls is that remote calls can fail because of unpredictable network problems. Also, callers generally must deal with such failures without knowing whether the remote procedure was actually invoked. Idempotent procedures (those that have no additional effects if called more than once) are easily handled, but enough difficulties remain that code to call remote procedures is often confined to carefully written low-level subsystems.

简单来说，RPC过程总是可能由于网络问题等不可预测的原因出错的，我们需要有一种途径来捕获并处理RPC过程中所发生的错误。`RpcController`就是为此而存在的，它定义了一些常用的错误处理的抽象接口，可以根据具体的场景进行实现。

鉴于`RpcController`的定义非常简单明确，并且是和具体场景紧密关联的，这里就不在上面花费更多精力了。以后业务逻辑逐渐复杂的时候，再根据需要case by case的进行实现即可。