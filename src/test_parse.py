import lark
from json import load

PARSER = lark.Lark(
    """
    ?exp: term (OR term)* (AND term)*
    ?term: symbol | NOT term | "(" exp ")"
    symbol: "A"
    AND: "*"
    OR: "+"
    NOT: "~"
    %ignore " "
    %ignore /[1-6]/
    %ignore "O6="
    %ignore "O5="
    %ignore "(A6+~A6)*"
    """,
    start="exp",
    parser="lalr",
)


qs = [
    "A1",
    "~ A1",
    "A1 + A2",
    "A1 + A2 + A3",
    "A1 * A2 * A3",
    "~ (A1 * A2 * A3) + ~ (A2 + A3)",
    "~ A1 * ~ A2",
    "O6=(A5*(~A6))+((~A5)*A6)",
    "O6=(A4*(~A1))+((~A4)*A1)",
    "O6=(A4*(~A1))+((~A4)*A2)",
    "O6=((~A4)*A3)+(A4*(~A3))",
    "O6=(A6+~A6)*(((~A3)))",
]

t = []
for q in qs:
    tree = PARSER.parse(q)
    tree.original = q
    t.append(tree)

extended_q = set()
with open("test_resources/aes128/iprec_output/aes128.json") as f:
    cells = load(f)["CELLS"]
    for c in cells.values():
        if "BEL_PROPERTIES" in c and "CONFIG.EQN" in c["BEL_PROPERTIES"]:
            extended_q.add((c["BEL_PROPERTIES"]["CONFIG.EQN"]))

extended_t = []
for q in extended_q:
    try:
        tree = PARSER.parse(q)
    except:
        print(q)
        raise Exception()
    tree.original = q
    extended_t.append(tree)


def compare_eqn(lh_eq, rh_eq):
    lh_trees = []
    for lh_child in lh_eq.children:
        if not isinstance(lh_child, lark.tree.Tree):
            try:
                rh_eq.children.remove(lh_child)
            except ValueError:
                return False
        else:
            lh_trees.append(lh_child)

    for lh_tree in lh_trees:
        for i, rh_tree in enumerate(rh_eq.children):
            if compare_eqn(lh_tree, rh_tree):
                rh_eq.children.pop(i)
                break
        else:
            return False
    return True


# test_eqn = t[-5:]

# for i, lh_eqn in enumerate(test_eqn):
#     tmp = [e for j, e in enumerate(test_eqn) if j != i]
#     for rh_eqn in tmp:
#         if compare_eqn(lh_eqn, rh_eqn):
#             print(f"{lh_eqn.original} equals {rh_eqn.original}")
#         else:
#             print(f"{lh_eqn.original} NOT equals {rh_eqn.original}")

for e in extended_t:
    for child0 in e.children:
        if isinstance(child0, lark.tree.Tree):
            if child0.data.value != "symbol":
                assert child0.children[0].value == "~"
            else:
                assert isinstance(child0, lark.token.Token)
