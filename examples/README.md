# Deep Faker Examples

This directory contains example simulation configurations for the deep_faker library.

## Examples

### E-commerce Simulation (`ecommerce.py`)
Simulates an e-commerce platform with:
- User registration and login flows
- Product browsing and purchasing
- Cart management
- Product reviews
- Multiple user states and behaviors

### Trading Platform Simulation (`trading.py`)  
Simulates a trading platform with:
- Trader registration and login
- Stock listings and price updates
- Market orders and fills
- Portfolio management
- Market alerts and monitoring

## Running Examples

Use the `deepfaker` CLI to run these simulations:

```bash
# Run from the project root
deepfaker --chdir examples ecommerce.py
deepfaker --chdir examples trading.py

# Or specify the full path
deepfaker examples/ecommerce.py
deepfaker examples/trading.py
```

## Output

All examples are configured to output events as JSON to stdout. You can redirect the output to a file:

```bash
deepfaker examples/ecommerce.py > ecommerce_events.json
```

## Customization

These examples demonstrate the key features of deep_faker:
- Event schema definitions with faker integration
- Entity state management
- Flow-based event generation
- Probabilistic flow control with AddDecay
- Entity filters and selections
- Multiple output handlers

Feel free to modify these examples or create your own simulation configurations!