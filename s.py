import random

s = "myAI.py examples/call_preflop.py examples/call_when_big_blind.py examples/call_when_blind.py examples/call.py examples/default.py examples/go_all_in_on_ace.py examples/go_all_in_on_pair.py examples/go_all_in.py examples/raise_by_big_blind_unless_raised.py examples/raise_by_half_of_stack.py examples/raise_by_pot_when_biggest_stack.py examples/raise_by_pot.py"
ls = s.split(" ")
for i in range(5):
    random.shuffle(ls)
    print("poker test 100 " + " ".join(ls))
