tags: 
- Python
- protobuf
comments: true
date: 2013-12-13 23:01:13 +0800
layout: post
status: public
title: 'Dive into Protocol Buffers Python API'
---

*Google Protocol Buffers*是Google使用的数据交换格式，在RPC协议和文件存储等有广泛的应用。其基本使用方法就不在赘述，可以参看*protobuf*的项目主页：<https://code.google.com/p/protobuf/>。本文的主要内容是剖析*protobuf*的Python API的具体实现。

由于我们需要的不仅仅是单纯的`message`结构，后续还希望使用*protobuf*的`service`实现RPC机制，因此本文会对这两部分内容进行分析。同时，为了使得剖析过程尽可能清晰，使用最简单的`message`和`service`结构作为研究对象，但是思路理清楚之后，更复杂的结构分析起来也是大同小异的。本文的以如下的proto文件及其编译出的代码作为剖析的起点：

```protobuf
package sample;

option py_generic_services = true;

message Void {}

message SampleMessage {
    required string message = 1;
}

service SampleService {
    rpc echo(SampleMessage) returns(Void);
}

```

使用`protoc`进行编译，即可得到对应的Python模块sample_pb2.py：

```bash
$ protoc --python_out=. sample.proto
```

生成的py代码超过100行，为了方便剖析，接下来按照结构分块进行剖析。

## message

对`message`的剖析，使用`message SampleMessage`的生成代码。

`message SampleMessage`对应的Python class的定义非常简单：

```python
class SampleMessage(_message.Message):
    __metaclass__ = _reflection.GeneratedProtocolMessageType
    DESCRIPTOR = _SAMPLEMESSAGE
```

这里涉及到的`__metaclass__`可以参看上一篇博文[《Python Meta-programming》](/blog/2013/12/12/python-meta-programming/)。

这里的`_SAMPLEMESSAGE`的具体定义是：

```python
_SAMPLEMESSAGE = _descriptor.Descriptor(
  name='SampleMessage',
  full_name='sample.SampleMessage',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='message', full_name='sample.SampleMessage.message', index=0,
      number=1, type=9, cpp_type=9, label=2,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=32,
  serialized_end=64,
)
```

看起来我们在proto文件中所定义的信息基本都在这里了，事实上如果查看`Descriptor`的代码，这个结构的琐碎细节也主要是用来组织数据而已。而动态生成相应class的机制，应该主要是由`GeneratedProtocolMessageType`实现的，就让我们来看一下其源码：

```python
class GeneratedProtocolMessageType(type):

    _DESCRIPTOR_KEY = 'DESCRIPTOR'

    def __new__(cls, name, bases, dictionary):
        descriptor = dictionary[GeneratedProtocolMessageType._DESCRIPTOR_KEY]
        bases = _NewMessage(bases, descriptor, dictionary)
        superclass = super(GeneratedProtocolMessageType, cls)

        new_class = superclass.__new__(cls, name, bases, dictionary)
        setattr(descriptor, '_concrete_class', new_class)
        return new_class

    def __init__(cls, name, bases, dictionary):
        descriptor = dictionary[GeneratedProtocolMessageType._DESCRIPTOR_KEY]
        _InitMessage(descriptor, cls)
        superclass = super(GeneratedProtocolMessageType, cls)
        superclass.__init__(name, bases, dictionary)
```

看到之前`__metaclass__`，其实我们就已经可以知道其是利用Python的Meta-programming机制来动态生成类的了。而上面这段`GeneratedProtocolMessageType`正是继承了`type`类，因此也是一个元类。

这里需要解释一下我们在使用`class`语法定义一个类的时候，传给Metaclass的三个参数的赋值内容。在这里我们可以简单的做一个实验，用如下方式定义一个类及其元类，并生成一个实例对象：

```python
import pprint

class MetaType(type):
    
    def __new__(cls, name, bases, dictionary):

        print 'name: ' + pprint.pformat(name)
        print 'bases' + pprint.pformat(bases)
        print 'dictionary' + pprint.pformat(dictionary)

        superclass = super(MetaType, cls)
        new_class = superclass.__new__(cls, name, bases, dictionary)
        return new_class
    
    def __init__(cls, name, bases, dictionary):
        superclass = super(MetaType, cls)
        superclass.__init__(name, bases, dictionary)

class A(object):
    __metaclass__ = MetaType
    
    CLASS_PROPERTY = 'CLASS_PROPERTY'
    
    def method(self):
        pass

instance = A()

```

运行该脚本得到如下输出结果：

	name: 'A'
	bases(<type 'object'>,)
	dictionary{'CLASS_PROPERTY': 'CLASS_PROPERTY',
	 '__metaclass__': <class '__main__.MetaType'>,
	 '__module__': '__main__',
	 'method': <function method at 0x110193b18>}

到这里，实例化`message`所对应的对象实例的过程就已经很清楚了：

首先protoc编译proto文件，生成对应与`message`的`Descriptor`以及一个简单的`class`骨架，这个`class`的主要作用就是通过类属性把对应`Descriptor`传给`GeneratedProtocolMessageType`。

而Python解释器真正要生成`message`所对应的`class`的时候，`GeneratedProtocolMessageType`会读取`Descriptor`中的属性和域的信息，动态的在生成的类实例中通过`InitMessage`（其最终是通过调用`setattr`）插入相应的属性和方法。

## service

相对于`message`来说，service的组成结构就更复杂一些，项目文档里对`service`也不够详细。概括来说，`service`主要是根据proto文件中的接口定义生成一个RPC调用的抽象层。这个抽象层是被设计成独立于任何RPC实现的，也就是说protobuf的作用只是帮助你在不同语言之间生成统一的调用接口，你可以在这个接口之下使用任何的通信机制来实现RPC过程。

虽然听起来很美，但是这样的抽象层也带来了过多不必要的间接层，在*protobuf 2.3*版本之后已经不鼓励继续使用`service`来实现RPC。但是一方面由于要取代`service`的`plugins`机制依然还在试验阶段，另一方面目前现有的很多的RPC实现依然是基于`service`，因此本文还是以`service`为研究对象来剖析如何利用`protobuf`来实现RPC机制。

利用*protobuf*的`service`来实现RPC，主要涉及三个对象：

1. `Service`： 提供了RPC可调用的方法的抽象层接口，由具体的服务或stub继承这个抽象接口，并进行具体实现。

2. `RpcChannel`：其负责与一个`Service`进行通信并调用其提供的RPC方法，通常情况下会在调用端实现一个`stub`对`RpcChannel`进行封装，通过调用`stub`的函数接口将调用行为转换为数据流通过`RpcChannel`进行传输，而不会直接使用`RpcChannel`。

3. `RpcController`：主要作用是提供一种可以控制RPC调用过程或者查明RPC过程中发生的错误的方式。

在这里我们依然结合之前的实例来对`service`进行剖析。同时，还会通过简单实现一个*Echo Service*的RPC调用来说明`service`的三个抽象对象是如何协作的。

同样的，我们从前面的proto文件编译出的py代码开始进行分析。其中对应`service`接口的两个抽象类的定义如下：

```python
class SampleService(_service.Service):
    __metaclass__ = service_reflection.GeneratedServiceType
    DESCRIPTOR = _SAMPLESERVICE

class SampleService_Stub(SampleService):
    __metaclass__ = service_reflection.GeneratedServiceStubType
    DESCRIPTOR = _SAMPLESERVICE
```

`SampleService`是为服务的**被调用端**提供的抽象接口，被调用段通过继承该接口并实现相应方法为调用端提供服务。

`SampleService_Stub`则是为**调用端**提供的`stub`的抽象接口。调用端需要做的事情则是继承该接口，将RPC函数接口的调用转化为数据流，并通过通信管道传递到被调用一端。

和`message`一样，这两个类只是一个骨架，其真正的实现是通过`__metaclass__`以及`Descriptor`进行实现。

我们首先来看一下`service`的`Descriptor`是什么样子的：

```python
_SAMPLESERVICE = _descriptor.ServiceDescriptor(
  name='SampleService',
  full_name='sample.SampleService',
  file=DESCRIPTOR,
  index=0,
  options=None,
  serialized_start=66,
  serialized_end=126,
  methods=[
  _descriptor.MethodDescriptor(
    name='echo',
    full_name='sample.SampleService.echo',
    index=0,
    containing_service=None,
    input_type=_SAMPLEMESSAGE,
    output_type=_VOID,
    options=None,
  ),
])
```

这个`Descriptor`依然包含了许多属性，但是我们其实更多的只需要关注`methods`这个属性，它是一个`list`，包含了我们在`service`中的定义的所有方法。之所以要关注`methods`，是因为在后续做RPC底层通信的具体实现的时候，主要需要传递的数据就是我们所调用的RPC方法及相应参数的描述。

接下来我们看一下被调用端的`Service`的元类**`GeneratedServiceType`**：

```python
class GeneratedServiceType(type):

    _DESCRIPTOR_KEY = 'DESCRIPTOR'

    def __init__(cls, name, bases, dictionary):
        if GeneratedServiceType._DESCRIPTOR_KEY not in dictionary:
            return
        descriptor = dictionary[GeneratedServiceType._DESCRIPTOR_KEY]
        service_builder = _ServiceBuilder(descriptor)
        service_builder.BuildService(cls)
```

这一层的定义依然非常简单，具体的细节我们需要进一步向前追溯到`_ServiceBuilder.BuildService`的代码才能一探究竟：

```python

class _ServiceBuilder(object):

    def __init__(self, service_descriptor):
        self.descriptor = service_descriptor

    def BuildService(self, cls):
        def _WrapCallMethod(srvc, method_descriptor,
                            rpc_controller, request, callback):
            return self._CallMethod(srvc, method_descriptor,
                           rpc_controller, request, callback)
        self.cls = cls
        cls.CallMethod = _WrapCallMethod
        cls.GetDescriptor = staticmethod(lambda: self.descriptor)
        cls.GetDescriptor.__doc__ = "Returns the service descriptor."
        cls.GetRequestClass = self._GetRequestClass
        cls.GetResponseClass = self._GetResponseClass
        for method in self.descriptor.methods:
            setattr(cls, method.name, self._GenerateNonImplementedMethod(method))

    def _CallMethod(self, srvc, method_descriptor,
                    rpc_controller, request, callback):
        if method_descriptor.containing_service != self.descriptor:
            raise RuntimeError(
                'CallMethod() given method descriptor for wrong service type.')
        method = getattr(srvc, method_descriptor.name)
        return method(rpc_controller, request, callback)

    def _GetRequestClass(self, method_descriptor):
        if method_descriptor.containing_service != self.descriptor:
            raise RuntimeError(
                'GetRequestClass() given method descriptor for wrong service type.')
        return method_descriptor.input_type._concrete_class

    def _GetResponseClass(self, method_descriptor):
        if method_descriptor.containing_service != self.descriptor:
            raise RuntimeError(
                'GetResponseClass() given method descriptor for wrong service type.')
        return method_descriptor.output_type._concrete_class

    def _GenerateNonImplementedMethod(self, method):
        return lambda inst, rpc_controller, request, callback: (
            self._NonImplementedMethod(method.name, rpc_controller, callback))

    def _NonImplementedMethod(self, method_name, rpc_controller, callback):
        rpc_controller.SetFailed('Method %s not implemented.' % method_name)
        callback(None)
```

`BuildService`函数主要做了两件事情：

1. 将自身的`_CallMethod`、`_GetRequestClass`、`_GetResponseClass`等公用方法的引用赋给新生成的类。其内部有一个`_WrapCallMethod`的嵌套函数，该嵌套函数存在的目的只是为了在使用`Service`实例对象进行方法调用`CallMethod`的时候可以把自身作为`srvc`参数传递给`_CallMethod`方法。

2. 将我们在proto中定义的`service`的RPC调用接口通过`setattr`“注入”到类的定义中。

这里尤其需要注意的是`_CallMethod`方法，可以看到这个方法主要的作用是讲传入的`method_descriptor`转化解析成为对`srvc`中相应方法的调用。因此，只要我们可以通过反序列化从通信的数据流中解析出RPC调用的`MethodDescriptor`，即可直接利用`_CallMethod`方法调用到相应的服务。这一点正是被调用端抽象接口需要实现的关键部分。

而调用端的**`GeneratedServiceStubType`**结构也是类似的：

```python
class GeneratedServiceStubType(GeneratedServiceType):

    _DESCRIPTOR_KEY = 'DESCRIPTOR'

    def __init__(cls, name, bases, dictionary):
        super(GeneratedServiceStubType, cls).__init__(name, bases, dictionary)
        
        if GeneratedServiceStubType._DESCRIPTOR_KEY not in dictionary:
            return
        descriptor = dictionary[GeneratedServiceStubType._DESCRIPTOR_KEY]
        service_stub_builder = _ServiceStubBuilder(descriptor)
        service_stub_builder.BuildServiceStub(cls)
```

`GeneratedServiceStubType`不仅包含了`GeneratedServiceType`对类对象的全部定义，还在此基础上通过`_ServiceStubBuilder`增加了`stub`所特有的属性。`_ServiceStubBuilder`的实现如下：

```python

class _ServiceStubBuilder(object):

    def __init__(self, service_descriptor):
        self.descriptor = service_descriptor

    def BuildServiceStub(self, cls):
        def _ServiceStubInit(stub, rpc_channel):
            stub.rpc_channel = rpc_channel
        self.cls = cls
        cls.__init__ = _ServiceStubInit
        for method in self.descriptor.methods:
            setattr(cls, method.name, self._GenerateStubMethod(method))

    def _GenerateStubMethod(self, method):
        return (lambda inst, rpc_controller, request, callback=None:
            self._StubMethod(inst, method, rpc_controller, request, callback))

    def _StubMethod(self, stub, method_descriptor,
                    rpc_controller, request, callback):
        return stub.rpc_channel.CallMethod(
            method_descriptor, rpc_controller, request,
            method_descriptor.output_type._concrete_class, callback)

```

其主要作用是实现对`RpcChannel`的包裹，从而将远端的RPC调用伪装成一个本地调用。这段代码里比较关键的两步：

1. `_GenerateStubMethod`生成的包裹方法将所有对`stub`方法的调用统一转换为对`_StubMethod`方法的调用，同时还将对具体方法的调用转化为了传入一个`MethodDescriptor`，使得后续进行通信的时候可以将调用行为序列化。
2. `_StubMethod`方法则进一步将方法的调用传递给了`RpcChannel.CallMethod`，从而可以通过`RpcChannel`将调用行为通过通信管道传递出去。也就是说，调用端抽象接口实现主要需要关注的是`RpcChannel.CallMethod`如何处理调用行为以及参数的序列化以及数据的传递。

既然如此，我们就来继续看一下`RpcChannel`的定义：

```python
class RpcChannel(object):
    def CallMethod(self, method_descriptor, rpc_controller,
                   request, response_class, done):
        raise NotImplementedError
```

RpcChannel接口非常简单明了，就是一个有待我们实现的`CallMethod`方法。回想一下`GeneratedServiceType`为我们的`Service`会添加一个非常相似的`CallMethod`方法。区别只在于被调用端的`CallMethod`会直接通过返回值传回`response`，而这里通过函数参数指定`response`的类型。所以，只要讲调用端的`CallMethod`和被调用端的`CallMethod`通过通信管道链接在一起，即可完成一个RPC过程！

目前为止，我们还遗漏了一项：`RpcController`。这个类主要是为了我们可以捕获RPC调用过程中的一些异常情况，并提供了一些额外的控制。具体实现方式因人而异，其定义也非常简单，仅仅是提供了一些基本的函数接口。这里不再赘述，具体要实现的内容可参看*protobuf Python API* `service.py`文件中`RpcController`代码的注释。

到目前为止，我们掌握的信息已经足以去利用`protobuf`具体实现一套PRC机制。在下一篇博文《Implement an Asynchronous RPC Basing on Protocol Buffers》中将基于本文的内容，具体说明如何构建一个可供RPC调用的`Echo Service`:)