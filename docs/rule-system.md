# Rule system contract

The core operates on open terms, relations and generic IR objects. It has no
inventory of source types, operators, ownership states, source functions or
class/trait names. Such meanings belong to selected STX libraries. A new type
need not be anticipated in a compiler enum.

## Selection and lexical scope

`effect relation(Pattern) when predicate => expression;` matches structure and
then evaluates a pure guard. All eligible peer rules are considered; two
matches diagnose ambiguity. Guards cannot build IR or create fresh identities.
`effect[fallback]` supplies a default only when no ordinary rule matches. Two
matching fallbacks are also ambiguous. This priority is explicit and identical
in dynamic and frozen compilers. Syntax rules offer the same explicit fallback
for generic identifier grammars. Otherwise the parser chooses longest matches,
with precedence/associativity for infix and precedence for prefix operators.

Syntax guards use `syntax category quotation when predicate => expression`.
The contextual parser supplies immutable data through `syntax.context()`;
guard evaluation cannot perform source IO, construct IR or create identities.
Only a unique selected item is materialized and passed to the explicit commit
relation. A commit returns `[newContext, itemList]`, which can omit compiler-only
declarations from the resulting program. Completed grammar results are cached
by category, token position, binding power and context identity. Peer conflicts
remain errors in dynamic and frozen parsers unless the calling frontend explicitly supplies a pure resolver.

`bind(pattern, value, body)` evaluates value once, destructures it, and evaluates
body in the extended lexical capture scope. Initializers see outer bindings;
body bindings shadow them. Repeated captures require equal values. Undefined
captures in loaded rule bodies are rejected before execution. `choose` evaluates
only its selected branch; `seq` evaluates its two operands in order.

Ordinary constructors and lists are structural values. Strings and integers
are distinct atoms; integers are canonical decimal values (`0001 == 1`,
`-0 == 0`). IR handles, logic variables, environments and hygienic symbols keep
identity. In particular, nested substitution never copies an SSA definition.

## Explicit disambiguation

The parser first applies ordinary-versus-fallback priority and longest matching
span. It collects same-span peers before reporting a conflict, so shorter peers
cannot prematurely reject a later longer production. A frontend may explicitly
supply a resolver to the source parser APIs. The resolver receives
`(category, candidates, context)` and returns a zero-based candidate index.
Each candidate is `[rawAST, literalCount, captureCount, ruleFile, ruleLine]`.
Only the selected AST reaches contextual materialization and commit. Candidate
ASTs are opaque templates; discarded actions are never executed to rank them.
Resolvers and ranking callbacks have the same purity restrictions as guards.

`dialects/parse.stx` exports `parse.specific`: it uses `rule.select` with
`[literalCount, -captureCount]`. A language can define a different pure callback,
combine this score with immutable namespace/type facts, and reject unsuitable
candidates with `[]`. Scores are signed 64-bit integers or lists of those
integers, ordered lexicographically; a longer equal-prefix list ranks higher.
Equal maximal scores and rejection of every candidate are diagnostics. Neither
loading order nor declaration order silently selects between peer rewrites.
An out-of-range resolver index is also a diagnostic.

```stx
// Selected explicitly by a raw frontend, not enabled globally.
effect resolve($category,$candidates,$context)
    => rule.select($candidates,"mydialect.rank",$context);
effect rank([$tree,$literals,$captures,$file,$line],$context)
    => [$literals,sub(0,$captures)];
```

This is local disambiguation of successful same-span productions, not a general
GLR/Earley parse forest. Arbitrary indirect left recursion and parent-dependent
reinterpretation of a previously selected child still require different grammar
rules or a future generalized parser. No automatic policy can infer a language's
intended interpretation from syntax alone.

Prefix literal, capture-led and infix-next-token indexes avoid scanning a whole
category on each parse. Wildcard/capture-led infix rules still participate, and
atomic/quoted terminals retain their lexical boundary behavior. Memoization is
per immutable context and fixed resolver, including failed parses. Normal unique
productions do not allocate candidate metadata or invoke a resolver.

## Execution limits

`--rule-budget` and `--parse-budget` select finite step budgets (1..1000000000,
default 1000000). `--rule-depth` and `--parse-depth` independently select semantic
recursion depth (1..1024, default 256). Projects may set integer values:

```toml
[limits]
rule_steps = 100000000
parse_steps = 100000000
rule_depth = 512
parse_depth = 512
```

Explicit CLI values override project values. Syntax guards/resolvers consume
the caller's remaining rule budget in every source parser API, and matching
candidate attempts consume the parse budget. Dynamic and AOT evaluators use the
same checks; generated dispatch routers do not consume additional semantic
depth. The STX expression reader and source-module graph retain their separate
256-level structural limits. Raising a budget does not remove recursion or
allocation costs; use iterative list/tree/rule primitives for long flat chains.
Unicode columns count code points, not grapheme clusters or terminal cell widths;
byte columns can process non-UTF-8 data. Tabs remain single columns until expanded.

## Generic tools

| Tool | Contract |
| --- | --- |
| `term(tag, children)` | Construct an arbitrary tagged term from a string and list. |
| `term.children(term)` | O(1) immutable direct-child list view of a constructor or list. Atoms are rejected. |
| `term.rebuild(original, children)` | Retain kind, tag and source provenance; reuse original if direct child identities match. No recursive comparison. |
| `tag / arg / size / term.kind` | Inspect tags, children, arity and representation kind. |
| `symbol(prefix)` | Fresh opaque identity, distinct even with identical printed prefixes. |
| `env.empty / put / get / contains` | Immutable scopes, arbitrary term keys, shadowing. Missing get is diagnosed. |
| `logic.fresh()` | Fresh unification variable; no assumed source-language meaning. |
| `logic.unify(a, b, substitution)` | Return `[success, substitution, reason]`. Structural constructor/list matching, variable dereference, occurs check, rollback on failure. |
| `logic.resolve(term, substitution)` | Resolve transitive substitutions throughout a structural value. |
| `apply(qualifiedRelation, argumentList)` | Invoke a selected ordinary relation, also in a frozen compiler. |
| `list.head / tail / prepend / concat / map` | Finite list decomposition and composition. `map` invokes a named relation. |
| `list.flatten(chunks)` | Merge a list of lists in order, copying each element edge once. |
| `syntax.context()` | Read an immutable contextual parser value during syntax guards/materialization/commit. |
| `source.parse_tokens(rows, category[, resolver])` | Parse items as syntax data. Default selection is strict. |
| `source.parse_tokens(rows, category, context, commit[, resolver])` | Parse selected items; commit receives context and item and returns `[newContext, itemList]`. |
| `source.parse_expression(rows, category[, resolver])` | Parse one complete expression; the four-argument form accepts context before resolver. |
| `rule.select(candidates, rankRelation, context)` | Return the zero-based unique maximum rank index. Pure callback receives candidate/context; empty rank rejects a candidate. |
| `target.toolchain(configurationJSON)` | Query target facts and installed SDK paths shared with native linking. Unavailable in pure guards. |
| `text.len / slice / contains / starts / ends` | Text operations; lengths and slice offsets use bytes. |
| `text.lines(text)` | Split LF, CRLF and CR physical lines in one pass; omit terminators and the synthetic row after a final terminator. Empty input gives `[]`. |
| `text.line_spans(text)` | Return `[startByte, endByte, oneBasedLine]` for the same physical lines without copying line text. |
| `text.columns(text, ranges[, unit])` | Extract zero-based half-open `[start,end]` ranges; default unit is `"byte"`, optional `"unicode"` counts validated UTF-8 scalars. Short rows clip to their length. |
| `text.expand_tabs(text, width)` | Expand tabs to the next tab stop in Unicode scalar columns; width 1..1024, reset after CR/LF. |
| `source.location(term)` | `[file, line, column]` source provenance. |
| `source.modules()` | Loaded module frames `[name, absolutePath, imports, localItems]` in dependency order. |

Representation kinds are 0 constructor, 1 text, 2 integer, 3 template capture,
4 relation call, 5 list, 6 operation, 7 SSA value, 8 region, 9 block, 10 logic
variable, 11 immutable environment, 12 hygienic symbol, 13 immutable list cursor. A language type is an
ordinary constructor, never a new representation kind. Source expressions
remain data until a selected library relation analyzes them.

The `tree` library supplies iterative traversal without AST-specific core code.
`tree.rewrite_with(value, enter, leave, context, state[, limit])` returns
`[rewritten, finalState]`. `enter(value, context, state)` returns either
`tree.Stop(replacement, state)` to prune, or
`tree.Descend(children, childContext, cookie, state)` to visit children.
`leave(cookie, rewrittenChildren, parentContext, state)` returns `[value, state]`.
State flows left to right through siblings; each sibling gets the specified child
context and leave gets the original parent context. Default iteration limit is
1,000,000 and all callback work also consumes the caller's rule budget.
`tree.rewrite(value, relation, context)` retains its post-order contract; lists
are rebuilt without invoking relation, and opaque values remain leaves.

`--unit item` invokes a relation for each item. `--unit program` invokes it once
with the entire dependency-ordered item list. A library can collect declarations,
check constraints, perform ownership analysis and then generate IR in separate
ordinary relations. The compiler imposes no order of language-specific phases.
Source module frames let a library implement its own export and visibility
policy. The shipped base library currently uses one flat function namespace.

Rule packages are composable. A selected `.stx` file may `use` several other
packages; dependencies are linked once and their syntax, constructors and
relations become available to the selecting project. `dialects/standard.stx`
is an ordinary example of this aggregation pattern. Composition does not guess
an execution order for same-named relations: if more than one imported module
defines `analyze`, the caller selects `ownership.analyze` or
`resources.analyze`, or defines an explicit facade relation that sequences the
analyses. The shipped `standard.stx` is such a facade: it analyzes ownership
and resource items first, then forwards base language items to the base
program checker and lowering.

An unqualified effect definition belongs to its declaring module: in
`mod externc`, `effect lower(...)` defines `externc.lower`. To extend an imported
relation, qualify the definition, for example `effect base.lower(...)` or
`effect types.repr(CPtr()) => "!llvm.ptr";`. Imported definitions and extensions
then participate in the same dispatch in both dynamic and frozen compilers.
`use base;` makes base's symbols visible; it does not redirect local definitions
to base. Constructor identity is linked separately, so qualified relation
extensions can use the imported library's existing terms.

The base program emitter calls the open `base.prepare_module` relation on
source items before collecting signatures and checking bodies. Its fallback is
the identity transform. A library can extend it to hoist static data, as
`dialects/externc.stx` does for C strings. Multiple libraries that replace the
whole phase must provide an explicit facade that sequences their transforms;
two matching ordinary phase rules are an ambiguity, not an implicit pass order.

## Exact numbers and policy

`int.parse` accepts decimal, hexadecimal, binary and octal spelling with digit
separators. The core lexer keeps C/LLVM hexadecimal floating spellings such as
`0x1.fp3` together; `numbers.stx` sends them through the same APFloat policy
as decimal literals. `int.neg/add/sub/mul/div/rem/and/or/xor/shl/shr/lt` compute exact
integers; division truncates toward zero and right shift is arithmetic.
`int.fits(value, width, signed)` tests a source range (`signed` is 0 or 1).
There is no implicit i32 narrowing. One operation has a 1,048,576-bit resource
limit, and evaluation has step/depth budgets; these limits are not source types.

`float.attr(spelling, MLIRFormat, rounding)` returns `[typedAttributeText, status]`
using APFloat semantics queried from the MLIR floating type. Rounding modes:
0 ties-to-even, 1 toward-zero, 2 toward-positive, 3 toward-negative, 4 ties-away.
Status bits are invalid=1, divide-by-zero=2, overflow=4, underflow=8, inexact=16.
The primitive reports these facts; the selected library decides the policy.

`float.convert(attribute, MLIRFormat, rounding)` changes floating formats;
`float.from_int(exactInteger, MLIRFormat, rounding)` converts an exact integer.
`float.add/sub/mul/div(leftAttribute, rightAttribute, rounding)` require equal
formats, while `float.neg(attribute)` preserves the format and changes the sign.
These tools return `[typedAttributeText, status]`, with the same IEEE status bits.
Typed attributes preserve the represented value; operations do not pass through
the host's `double`. Rounding modes match `float.attr`.

`float.to_int(attribute, width, signed)` returns `[exactInteger, status]`, truncates
toward zero, and uses signed=0 for unsigned or 1 for signed. Width has the same
resource bound as exact integers. The integer is not a usable result when status
contains invalid=1; the caller must check that fact before using it.
`float.compare(leftAttribute, rightAttribute)` returns -1, 0, 1, or 2 for less,
equal, greater, or unordered. Equal formats are required, signed zeros compare
equal, and unordered is preserved rather than silently ordered.

`types.stx` also defines the target-sized `index` type. Its exact integer
literal is kept unbounded in the rule layer and lowered as MLIR `index`, so
shape/offset dialects do not have to pretend that index is `i32`.
The same library defines shaped aggregate descriptors. `vector<N, T>` and
`tensor<N, T>` are the rank-1 spelling; a rank-2 or higher shape is written as
`vector<2 x 3, f32>` or `tensor<2 x 3, f32>` and lowers to MLIR
`vector<2x3xf32>` / `tensor<2x3xf32>`. Dimensions are checked as positive exact
integers before lowering, and the shape remains an ordinary list term, so a
device dialect can add its own shaped type without extending the core.
The optional `shapes.stx` package adds static indexing to base expressions:
`a[1][2]` checks each dimension and lowers a rank-2 vector through two
`vector.extract` operations. It also lowers rank-1 tensor indexing through
`tensor.extract`. Out-of-range static positions are rejected during source
checking; higher-rank tensor slicing and runtime indices are not yet defined by
this package. The `standard.stx` aggregate loads `shapes` automatically.
`numbers.stx` checks integer literal bounds, rounds real literals to nearest
ties-to-even, allows inexact representation, and rejects invalid/overflow/
underflow. The source type library covers IEEE binary16/32/64/80/128, bfloat16,
TF32, and MLIR's FP8/FP6/FP4 formats; the same APFloat path parses and rounds
their literals. `base.stx` rejects implicit source-type mixing. Signed and unsigned
source types share signless MLIR integer storage but select distinct division,
remainder and ordering operations. Runtime integer add/sub/mul are modular;
division retains arith's preconditions. Runtime traps/checks are not yet supplied.

## Library extension and verification

`types.stx` defines structural type terms, representation rules and a structural
constraint solver. Other libraries may extend `types.solve_one` with new
constraint constructors; the core solver does not classify those constraints.
`base.stx` supplies contextual checking, hygienic parameter/local bindings,
whole-program signature collection and lowering. `money.stx` extends its open
`constant/opcode/predicate` relations and `types.repr` for an unknown `Cents()`.
No compiler source change or new native plugin is needed for that extension.

`base.stx` also defines ordinary `var` declarations, assignment, `while` and
`if`/`else` statements inside functions. `let` and parameters are immutable;
assignment checks the binding's mutability and exact source type. Conditions
must be `bool`. Nested blocks have lexical scope, and a `return` inside a
branch or loop terminates that function path. The current function spelling
still requires a final return statement. Explicit integer `as` casts support
truncation, signed/unsigned extension, and same-width signedness changes;
other conversions can extend the open `cast_opcode` relation.

The shared continuation builder lowers these statements to arbitrary CFG
blocks rather than algorithm-specific templates. Mutable locals use rank-zero
stack memrefs allocated once in the entry block; initializers execute at their
source position, including on each loop iteration. LLVM scalar promotion removes
the stack slots at O2 when their addresses do not escape. `mlir.with_block`
evaluates an expression in a selected block and returns its result, restoring
the previous insertion point even on failure; `mlir.in_block` retains its
existing block-valued result. Both have matching dynamic and frozen semantics.
The runtime benchmarks in `benchmarks/runtime` load only `base.stx` and contain
ordinary `.nru` functions, parameters, calls, arithmetic and loops.

`resources.stx` demonstrates per-resource move state and lexical loans using
ordinary constructors and immutable scopes. Its branch rule recursively joins
resources into `MaybeMoved` when paths disagree and requires every active loan
to close on every path; nested branches use the same join relation. It does not
claim a complete borrow checker: interprocedural loans and destructor insertion
still require further language rules and runtime lowering.

MLIR builders support arbitrary operation names/types/attributes, multiple
regions/blocks, block arguments, successors and backedges. IRDL and native
plugins provide custom dialect verification, interfaces and passes. Semantic
rules must generate legal IR and choose a compatible target pipeline.

AOT freezing compiles syntax/effect patterns, guards, local binders and RHS
expressions to native Vyx functions while preserving these contracts. Generic
tools and captured dynamic terms use shared runtime support. Freezing eliminates
runtime STX loading and static pattern interpretation; it does not eliminate all
allocations or prove arbitrary language rules correct. Recursive rules may fail
to converge, and incompatible extensions may be ambiguous.

`tests/rules.py` validates these contracts, numeric boundaries, user type
extensions, borrow conflicts, dynamic/AOT result and diagnostic parity, and
native execution at O0/O3 in a process that cannot launch children.


Rule callbacks used by apply/fold/map/iterate/unfold run in nested allocation
scopes. Only new values reachable from the callback result, cached Engine roots,
or IR effects survive the boundary; borrowed caller values remain stable.
Immutable list edges and persistent environment tree nodes are traced once per
scope with iterative queues. Surviving child-scope allocations transfer to the
parent scope, and dead slots are reused. This is scoped reclamation rather than
whole-program garbage collection; allocations outside callback boundaries can
still remain until the compilation ends. The same facility serves dynamic and
frozen rules without any language-specific object or ownership inventory.

Dynamic effect dispatch indexes relation/arity and the first argument's fixed
shape, merging wildcard candidates in source order before matching all eligible
peers. Entry-name and effect-index caches are invalidated when linking appended
rules, so an overlay still participates in overload and ambiguity decisions.


External token rows may opt into kind 14, an indivisible terminal. A quoted
terminal such as `"++"` or an ordinary punctuation literal matches its exact
spelling. Identifier/number/string captures do not consume it. Kind 5 keeps its
existing core punctuation segmentation; the frontend chooses which contract it
needs. Numeric rows with a plain decimal spelling can also use the `int` capture
category, while suffixes, fractions and other numeric spellings stay under
`number`. Dynamic and frozen parsers share both contracts.


`env.entries(environment)` returns the snapshot's current unique `[key, value]`
bindings. Enumeration order is not insertion order. Environment storage is
opaque: semantic packages must use this interface rather than traverse a parent
chain with arg/size. Persistent old snapshots keep their own roots and bindings.
Enumeration consumes the rule budget and works in pure guards and frozen code.

The `storage` rule library represents a target object image with
`Scalar(IRType, valueBits, objectBits, kind)` and
`Aggregate(IRType, objectBits, [[bitOffset, LLVMIndex, childShape], ...])`.
Kinds are `integer`, `float`, and `pointer`. `storage.reinterpret(value,
sourceShape, destinationShape)` projects the supplied LLVM values without
arithmetic conversion. Aggregate members must be ordered, nonoverlapping and
inside their parent object. Offsets describe low-order image bits explicitly,
so an adapter must select its target byte order. Padding starts at zero and
object widths are limited to 1,048,576 bits.

The source traversal extracts scalar fragments once. A monotone cursor builds
destination scalar windows, preserving a complete symbolic pointer window
without assembling or shifting a whole-object integer. Traversal work is linear
in the number of fragments and overlapping windows for ordered layouts; LLVM
integer operations depend on scalar window widths. Explicit `pack`/`unpack`
remain available, but `reinterpret` no longer builds a large integer for each
aggregate. The library knows no source-language types. C11 supplies the LLP64
layout adapter and aligned integer units for union storage. Generic tests in
`tests/storage.py` cover partial cursors, shrinking, growth, holes and malformed
source/destination layout facts.

Before native LLVM translation, the backend attaches temporary
`naru_backend.require_constant` facts to initializer operations. A translation
interface checks the actual LLVM result and disposes of unattached instruction
dependencies before reporting a nonconstant result. This prevents LLVM module
destruction from aborting on retained symbol users. It does not whitelist source
constructs or LLVM operation names, and the temporary facts are removed after
translation. Pure LLVM symbolic casts remain constants; transformations that
cannot be represented by the selected LLVM backend produce a diagnostic.

Frozen compiler metadata uses length-prefixed constant tables loaded once at
startup. Syntax/effect patterns, guards and bodies still execute native Vyx
functions. Candidate scheduling shares the indexed dynamic dispatcher, so
dynamic overlays and frozen peers follow the same matching order and conflict
contract. Generated native routers are split into bounded groups; the host
optimizer no longer receives a single duplicated graph for all effects.
Scalar constants and captures share a native leaf helper rather than generating
a function for each occurrence. Captures return their bound value directly.
Dynamic evaluation and native frozen bodies use the same step/depth checks;
dispatch routers do not consume semantic recursion depth. AOT build manifests
record generated source size, build time and sampled process-tree private commit
memory, with the sampling interval stated explicitly.

`tests/parser_perf.py --baseline <saved-core.exe>` compares identical rule files,
inputs and resulting AST hashes. It records repeated time and peak commit for a
2003-rule grammar, recursive shared prefixes and the actual system stdio frontend.
These are compiler frontend measurements, not generated-program runtime results.
The ranking loop keeps only native scalar scores and immediately reclaims each
callback's temporary terms; input AST candidates remain borrowed immutable data.
