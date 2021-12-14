tags: 
- Python
comments: true
date: 2013-12-12 23:47:23 +0800
layout: post
status: public
title: 'Python Meta-programming'
---

在实际工作中，Python的Meta-programming的使用其实是比较少的。另一方面使用这个语言特性很容易导致代码可维护性下降，所以应该是尽可能的避免使用的。

但是对于一些特殊的代码，例如目前正在研究的*Google Protocol Buffers*的Python API，由于其需要根据用户定义的proto文件生成特定的class，因此需要对class很强的定制能力。而这正是Meta-programming所擅长的事情。

Python的新式类可以通过通过两种方式在运行时修改类的定义，通过`__new__`方法，以及通过指定`__metaclass__`。protobuf主要使用的就是后者。本文参考《Expert Python Programming》中"Meta-programming"章节，对这两种方法分别进行说明。

## 使用`__new__`方法在实例化过程中修改类定义 ##

`__new__`方法被称为`meta-constructor`，每个类在实例化过程中都会首先调用`__new__`方法得到对象实例，之后才会去调用可能存在的`__init__`方法。

一个简单的实验：
```python
class MyClass(object):

    def __new__(cls):
        print '__new__ called'
        return object.__new__(cls)
    
    def __init__(self):
        print '__init__ called'

instance = MyClass()
```

运行这段脚本可以看到输出结果：

```bash
__new__ called
__init__ called
```

因此通过这种方式，我们可以通过重载`__new__`方法来更改一个类的实例化行为。一个典型的应用是通过重载`__new__`方法来实现单例模式：

```python
class Singleton(object):

    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(Singleton, cls).__new__(cls, *args, **kwargs)
        return cls._instance
```

另外一些关键的初始化可以在`__new__`函数内进行。即使该类被继承，并且子类忘记调用基类的`__init__`方法，依然可以保证代码的正确运行，或者至少给出相应的提示。threading模块的Thread类就是用这种机制来避免未初始化的子类。


## 更加自由灵活的`__metaclass__`

元类(`Metaclass`)，简单说来就是用来生成类的类。这里我们把`class`本身称作“类对象”，由“类对象”实例化得到的对象称作“实例对象”。在Python中，默认情况下所有的类对象都是`type`类的实例对象，即`type`类是所有`class`的`Metaclass`，甚至包括type类自身的`Metaclass`也是`type`类。

### Python的`type`关键字

Python中的`type`关键字是Python语言里少数违反单一性原则的特例之一：

1. 当使用单参数调用`type(instance)`的时候，`type`是一个函数，其作用是返回`instance`（实例对象）的`class`类型。
2. 当使用三参数调用`type(classname, base_types, dict)`的时候，`type`是一个类，其作用是根据给定参数实例化出一个`class`（类对象）。

前面说到所有`class`都是`type`类的实例，可以很容易的根据`type`的这两种用法通过代码来验证一下：

```pycon
>>> class A(object):
...     pass
... 
>>> instance = A()
>>> type(instance)
<class '__main__.A'>
>>> type(A)
<type 'type'>
>>> type(type)
<type 'type'>
```

### 使用自定义的`Metaclass`生成类对象

想要使用自定义的`Metaclass`生成类对象，首先弄清楚Python默认的`type`是如何作为`Metaclass`生成类对象的。其实根据前面`type`的第二种用法，你应该也已经猜到大概了，我们只需要给定所需要生成的`class`的名字、基类以及相应的属性和方法，就可以由`type`实例化出我们所要的类对象。也就是说，如下两段代码可以看做是等价的：

```python
def method(self):
    return 0

MyClass = type('MyClass', (object,), {'method': method})

instance = MyClass()
```

```python
class MyClass(object):
    def method(self):
        return 0

instance = MyClass()
```

Python为指定类的自定义`Metaclass`提供了更加便捷的语法`__metaclass__`，其具体使用方式如下：

```python
class MyClass(object):
    __metaclass__ = MyMetaClass
	
    def some_method:
        pass
```

其中，自定义的`Metaclass`(`MyMetaClass`)只需要满足的如下两个条件（只要满足这些条件即可，自定义的`Metaclass`不必一定是一个类）：

1. 可以接受与`type`相同的参数列表，也就是类名、基类的元组以及属性的字典。
2. 返回一个类对象。

借用《Expert Python Programming》上一个例子来简单说明`__metaclass__`的用法，这里为没有指定`docstring`的类在生成阶段指定一个默认的`docstring`：

```python
def type_with_default_doc(classname, base_types, dict):
    if '__doc__' not in dict:
        dict['__doc__'] = 'default doc'
    return type(classname, base_types, dict)

class MyClassWithDoc(object):
    __metaclass__ = type_with_default_doc
```

`__metaclass__`的用法其实就是这样，相对来说还是比较简单的。但是正如开篇提到的那样，在不是非常必要的时候，还是应该尽量避免使用这样的语言特性，因为使用过多`Metaclass`的项目必然是很难维护的。

而本文的目的，主要还是为剖析*Google Protocol Buffers*的Python API的实现做铺垫。其内部主要就是使用`__metaclass__`机制来生成由proto文件定义的结构体和service。这部分内容会在后续的博文中进行更详细的阐述：）