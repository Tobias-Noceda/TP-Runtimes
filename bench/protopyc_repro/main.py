# Imports the compiled modules (each <name>.so next to this file, no .py).
import sys

case = sys.argv[1]
if case == "clash":
    import mod_a, mod_b
    a = mod_a.A()
    b = mod_b.B(1)          # expected: B.__init__ ; bug: runs A.__init__ -> TypeError
    print("clash ok:", a.who, b.who, b.x)
elif case == "pep695":
    import pep695
    print("pep695 ok:", pep695.Box(1).v)
elif case == "builtin_generic":
    import builtin_generic
    print("builtin_generic ok:", builtin_generic.IntList([1]))
elif case == "generic_base":
    import generic_base
    print("generic_base ok:", generic_base.Child.__mro__)
