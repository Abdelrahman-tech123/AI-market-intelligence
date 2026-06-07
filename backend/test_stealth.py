from playwright_stealth import Stealth
import inspect

# Get all methods and attributes
debug_print("Stealth class methods and attributes:")
debug_print(dir(Stealth))
debug_print("\n" + "="*50)
debug_print("Stealth __init__ signature:")
debug_print(inspect.signature(Stealth.__init__))

# Try to instantiate and see what works
stealth = Stealth()
debug_print("\n" + "="*50)
debug_print("Stealth instance methods:")
debug_print([m for m in dir(stealth) if not m.startswith('_')])
