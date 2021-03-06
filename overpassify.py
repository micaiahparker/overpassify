import ast, _ast
from functools import singledispatch
from inspect import getsource
from types import FunctionType

from dill.source import getsource as dillgetsource

@singledispatch
def overpassify(query):
    raise TypeError('Overpassify does not support {}.'.format(type(query)))


@overpassify.register(str)
def _(source):
    return parse(source)


@overpassify.register(FunctionType)
def _(func):
    try:
        source = getsource(func)
    except Exception:
        source = dillgetsource(func)
    return overpassify(source)


@singledispatch
def parse(source, **kwargs):
    print(source)


@parse.register(str)
def _(source, **kwargs):
    tree = ast.parse(source).body[0].body
    return '\n'.join(parse(expr) for expr in tree)


@parse.register(_ast.Assign)
def _(assignment, **kwargs):
    return '({};) -> {};'.format(
        parse(assignment.value),
        parse(assignment.targets[0])
    )


@parse.register(_ast.Expr)
def _(expr, **kwargs):
    return parse(expr.value)


@parse.register(_ast.Name)
def _(name, **kwargs):
    return '.' + name.id


@parse.register(_ast.BinOp)
def _(binary_operation, **kwargs):
    return parse(binary_operation.op, left=left, right=right)


@parse.register(_ast.Add)
def _(_, **kwargs):
    return '({}; {})'.format(parse(kwargs['left']), parse(kwargs['right']))


@parse.register(_ast.Sub)
def _(_, **kwargs):
    return '({} - {};)'.format(kwargs['left'], kwargs['right'])


@parse.register(_ast.keyword)
def _(keyword, **kwargs):
    return keyword.arg, parse(keyword.value)


@parse.register(_ast.Call)
def _(call, **kwargs):
    name = parse(call.func)[1:]
    if name.endswith('.intersect'):
        overpasstype = (name.split('.')[0]).replace('set', '').lower()
        return overpasstype + ''.join((parse(arg) for arg in call.args))
    if name.endswith('.filter'):
        overpasstype = (name.split('.')[0]).lower()
        return overpasstype + parse(call.args[0])
    elif name == 'out':
        if len(call.args) == 0:
            element = '._'
        else:
            element = parse(call.args[0])
        out_channels = {parse(kwarg)[0] for kwarg in call.keywords}
        ret = ''
        if 'count' in out_channels:
            ret += element + ' out count;\n'
            out_channels.remove('count')
        return ret + element + ' out {};'.format(' '.join(out_channels))
    elif name == 'Set':
        return '({})'.format(
            '; '.join((parse(arg) for arg in call.args))
        )
    elif name in {'Way', 'Node', 'Area'}:
        overpasstype = (name.split('.')[0]).lower()
        if len(call.args) == 1:
            arg = parse(call.args[0])
            try:
                int(arg)
                return '{}{}({})'.format(
                    overpasstype,
                    ''.join('[{}={}]'.format(*parse(kwarg)) for kwarg in call.keywords),
                    arg
                )
            except Exception:
                return '{}{}({})'.format(
                    overpasstype,
                    ''.join('[{}={}]'.format(*parse(kwarg)) for kwarg in call.keywords),
                    'area' + arg
                )
        elif len(call.args) == 0:
            return '{}{}'.format(
                overpasstype,
                ''.join('[{}={}]'.format(*parse(kwarg)) for kwarg in call.keywords)
            )
        else:
            raise IndexError('Calls to locators do not support multiple positional arguments')
    else:
        raise NameError('{} is not the name of a valid Overpass type'.format(name))


@parse.register(_ast.Attribute)
def _(attr, **kwargs):
    return '{}.{}'.format(parse(attr.value), attr.attr)


@parse.register(_ast.Str)
def _(string, **kwargs):
    return '"{}"'.format(string.s)


@parse.register(_ast.Num)
def _(num, **kwargs):
    return "{}".format(num.n)
