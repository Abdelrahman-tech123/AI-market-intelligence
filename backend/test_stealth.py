from playwright_stealth import Stealth
import inspect

# Get all methods and attributes
print("Stealth class methods and attributes:")
print(dir(Stealth))
print("\n" + "="*50)
print("Stealth __init__ signature:")
print(inspect.signature(Stealth.__init__))

# Try to instantiate and see what works
stealth = Stealth()
print("\n" + "="*50)
print("Stealth instance methods:")
print([m for m in dir(stealth) if not m.startswith('_')])
