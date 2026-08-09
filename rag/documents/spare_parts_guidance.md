# Spare Parts Management Guidance

## Critical Spare Parts Strategy

### Classification
- **Critical (A)**: Failure causes immediate plant shutdown or safety incident. Stock 1-2 units on-site.
- **Essential (B)**: Failure causes production loss within 24 hours. Stock 1 unit on-site or 48hr delivery.
- **Desirable (C)**: Failure causes minor disruption. Stock min/max levels, standard lead time.

### Pump Spares (BFP-101, BFP-102, PUMP-401, PUMP-402)

| Part | Classification | Min Stock | Lead Time | Notes |
|------|---------------|-----------|-----------|-------|
| Mechanical Seal Kit | Critical | 1 | 4 weeks | Replace at 12 months or on leak |
| DE Bearing (SKF 7315 BECBM) | Critical | 1 | 2 weeks | Replace at 24 months |
| NDE Bearing (SKF 6314 C3) | Critical | 1 | 2 weeks | Replace at 24 months |
| Oil Cooler Bundle | Essential | 0 | 6 weeks | Refurbish option available |
| Coupling Element Set | Essential | 2 | 1 week | Inspect quarterly |
| Suction Strainer Element | Desirable | 2 | 1 week | Clean/replace monthly |
| Wear Rings | Essential | 1 | 8 weeks | Measure at overhaul |
| Impeller | Desirable | 0 | 12 weeks | Repair vs replace analysis |

### Compressor Spares (COMP-201, COMP-202)

| Part | Classification | Min Stock | Lead Time | Notes |
|------|---------------|-----------|-----------|-------|
| Thrust Bearing (Tilting Pad) | Critical | 1 | 8 weeks | Monitor vibration trend |
| Journal Bearings (Set) | Critical | 1 | 6 weeks | Replace at 36 months |
| Labyrinth Seals | Essential | 1 | 4 weeks | Check clearance annually |
| Anti-surge Valve Trim | Critical | 1 | 6 weeks | Test quarterly |
| Lube Oil Pump (Standby) | Critical | 1 | 10 weeks | Auto-start verified monthly |

### Motor Spares (MOTOR-301, MOTOR-302)

| Part | Classification | Min Stock | Lead Time | Notes |
|------|---------------|-----------|-----------|-------|
| DE Bearing (6318 C3) | Critical | 1 | 2 weeks | Replace at 24 months |
| NDE Bearing (6316 C3) | Critical | 1 | 2 weeks | Replace at 24 months |
| RTD Set | Essential | 1 | 3 weeks | Critical for temp monitoring |
| Space Heaters | Essential | 2 | 1 week | Prevent condensation |
| Terminal Box Gaskets | Desirable | 5 | 1 week | Replace on opening |

## Inventory Management Rules

1. **Monthly Review**: Check critical spares stock levels
2. **Reorder Point**: Trigger at min stock level
3. **Lead Time Buffer**: Add 20% to supplier lead time
4. **Obsolescence Check**: Annual review of slow-moving items
5. **Cross-Plant Sharing**: Emergency transfer between NorthPlant/SouthPlant/EastRefinery

## Procurement Process
1. Maintenance identifies need → Creates requisition in CMMS
2. Planner verifies stock/spec → Approves
3. Procurement sources (preferred vendor vs spot buy)
4. Goods receipt → Inspection → Stock update
5. Critical spares: Quality certs required