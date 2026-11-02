# Findings log — Runtimes Concurrentes final

Short record of every bug / behaviour found while porting and benchmarking tp1.
Status: **fixed** (with PR material), **workaround** (in tp1, runtime untouched),
**open** (recorded, not fixed).

| # | Where | Finding | Status | Evidence |
|---|---|---|---|---|
| F1 | protoCore + protoPython | Tuple hash `h*1000003 ^ eh` cancels across nesting → `(a,(b,c))`/`(b,(a,c))` collide; tuple hashes treated as exact → distinct Sokoban states merged, soko_01 unsolvable | **fixed** (xxHash mix, branches `fix/tuple-hash-xxhash`) | tests `HashedCollection.NestedTuplesSwappingElementsAcrossLevelsHashApart`, `protopy_tuple_hash_nested`; night block 7 (old vs fixed) |
| F2 | protoPython | `@dataclass` on a class without annotations → `KeyError: 'pop'` | workaround (no-op decorator removed) | — |
| F3 | protoPython | Name mangling (`__x`) not applied inside comprehensions/genexprs | workaround (`__x` → `_x`) | — |
| F4 | tp1 A* | Hang on unsolvable boards (workers blocked in `get()`) | **fixed** (`shutdown` in `close()`) | night block 0 |
| F5 | tp1 A* | Check-then-act race on `smallest_g_score`/`previous_state`: lost updates (813–1063 per soko_01 run without GIL, 3 with GIL); can return a **non-optimal path** (board1: 7 steps instead of 5, 3.14t w=8) | **fixed behind flag** (`locks=True`, 64 striped locks) | `regressions` counter; night blocks 0, 3, 4 |
| F6 | protoPython | Single dict/set/list ops are atomic without GIL (snapshot + CAS retry, `publishDictState`); `d[k] += 1` loses ~80 % | behaviour (demo) | `bench/lostwrites.py`; night block 0 |
| F7 | protoPython | Intermittent exit with no output: P110, 8 workers (1 of 4 runs) | **open** | night block 6 records exit codes |
| F8 | protoPython | `sys._is_gil_enabled()` returns `True` on a GIL-free runtime; version reports `3.14.0` | **open** (cosmetic) | `bench/lostwrites.py` header line |
| F9 | protopyc | Generated functions exported with module-independent names (`py_func___init___1`) + `dlopen(RTLD_GLOBAL)` → module B's calls bind to module A's function (`BoardManager(board)` ran `AStar.__init__`) | **open**, workaround `-Wl,-Bsymbolic` | `bench/protopyc_repro/repro.sh` case `clash`; `scratchpad/pyc/FINDINGS.md` |
| F10 | protopyc | PEP 695 type parameter used in a base (`class Box[T](Base[T])`) → `NameError: name 'T'` | **open** | repro case `pep695` |
| F11 | protopyc | Generic alias as base (`class C(Base[int])`, `typing.Generic`) → `TypeError: bases must be types` (interpreter OK) | **open** | repro case `generic_base` |
| F12 | protopyc | Compiled `sokoban_board` gives `IndexError`; compiled `a_star` alone >120 s on soko_01 (22 s interpreted) | **open**, not investigated | `scratchpad/pyc/FINDINGS.md` |
| F13 | protoPython | `types.GenericAlias` (`list[int]`) has no `__mro_entries__` and is not callable → `class IntList(list[int])` builds a broken class | **open** — debrief below | repro case `builtin_generic`; probe below |

---

## F13 debrief — `class IntList(list[int])` (pre-analysis, not fixed)

### Symptom

```python
class IntList(list[int]):
    pass
IntList([1])   # protopy: TypeError: 'GenericAlias' object is not callable ; CPython: [1]
```

Not used by tp1; found while writing `bench/protopyc_repro/`. Does **not** affect any benchmark.

### Probe (protopy vs CPython 3.14)

| expression | protopy | CPython |
|---|---|---|
| `type(list[int])` | `<class 'GenericAlias'>` | `types.GenericAlias` |
| `list[int].__origin__` | `list` ✓ | `list` |
| `list[int].__mro_entries__((...))` | **AttributeError** | `(list,)` |
| `list[int]([1])`, `dict[str,int]()` | **TypeError: not callable** | `[1]`, `{}` |
| `class IntList(list[int])` | "succeeds", repr `str[list[int]]` | `<class IntList>` |
| `IntList.__bases__` / `__mro__` | `()` / `(GenericAlias, object)` | `(list,)` / `(IntList, list, object)` |
| `IntList.__orig_bases__` | AttributeError | `(list[int],)` |
| `class L(typing.List[int])` → `L([1])` | **works** | works |

`typing.List[int]` works because typing's Python-level `_GenericAlias` defines
`__mro_entries__` and `__call__`; only the **native** `GenericAlias` lacks them.

### Root cause (where to look)

1. Class creation already implements PEP 560:
   `PythonEnvironment::buildClass`, `protoPython/src/library/ExecutionEngine.cpp:4925-4975`
   — for every base that is not a class, it looks up `__mro_entries__` and replaces it.
2. The native GenericAlias prototype is built in
   `protoPython/src/library/BuiltinsModule.cpp:13058-13084` with only `__new__`,
   `__repr__`, `__eq__`, `__hash__`, `__or__`, `__ror__`, `__mro__`.
   **No `__mro_entries__`, no `__call__`.** (`py_genericalias_new` at ~6081 stores
   `__origin__` / `__args__`.)
3. Most likely chain: no `__mro_entries__` → `buildClass` keeps the alias as a base
   unchanged → the metaclass call uses the alias object itself as the class's parent,
   which matches `__mro__ == (GenericAlias, object)` and `__bases__ == ()`.
   Checked from Python: `isinstance(list[int], type)` is `False` and
   `list[int].__class__` is `GenericAlias` (same as CPython), so the alias is probably
   **not** taken for a class. Still unverified at C++ level: the prototype sets
   `__class__ = type` (line ~13061) and `isActuallyAClass` might look at that — if adding
   `__mro_entries__` alone does not fix it, check `isActuallyAClass(list[int])` next.

### Proposed fix (est. 45–60 min with tests)

- `py_genericalias_mro_entries(self, bases)` → `(self.__origin__,)`; register as
  `__mro_entries__` on the prototype.
- `py_genericalias_call(self, *args, **kw)` → call `self.__origin__(*args, **kw)`; then
  try to set `__orig_class__ = self` on the result, ignoring failures (CPython does the
  same; builtins like `list` reject it silently).
- Only if that is not enough: make `isActuallyAClass` return false for GenericAlias instances (check the
  prototype chain for `getGenericAliasProto()`), or drop `__class__ = type` and give the
  alias its own `__class__` (`types.GenericAlias`).
- Regression test `test/regression/genericalias_base.py` + CMake `add_test` (pattern of
  `protopy_tuple_hash_nested`): `list[int]([1]) == [1]`, `dict[str,int]() == {}`,
  `class IntList(list[int])` → `__bases__ == (list,)`, `__orig_bases__ == (list[int],)`,
  `IntList([1]) == [1]`, `isinstance(IntList(), list)`.
- Full `ctest --test-dir build_release -j8` (1151 tests) before trusting it.
- **Caution:** rebuilding `build_release/protopy` changes the runtime the benchmarks used.
  Do it **after** the night results are final, and record the new commit in the slides.
- Related but separate: protopyc's F11 (`bases must be types`) means compiled classes do
  not go through the same PEP 560 path as `buildClass`, or reject non-type bases before it.
