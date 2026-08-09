# Motor Maintenance Procedure - General Guidelines

## Scope
Applies to all induction motors (LV and MV) across NorthPlant, SouthPlant, and EastRefinery.

## Asset Types Covered
- MOTOR-301 (Unit 3, SouthPlant, 1.2 MW, 6.6 kV)
- MOTOR-302 (Unit 3, SouthPlant, 900 kW, 6.6 kV)
- All other plant motors

## Preventive Maintenance Schedule

### Monthly (SOP-MOT-M01)
1. Visual inspection
   - Check for oil leaks, corrosion, damage
   - Verify mounting bolts tight
   - Check coupling guard secure
2. Temperature measurement
   - Bearing temperatures (DE/NDE)
   - Winding temperature (RTD)
   - Ambient temperature
3. Vibration screening
   - Overall vibration (mm/s RMS)
   - Compare to baseline
4. Electrical checks
   - Motor current (all phases)
   - Voltage balance
   - Power factor

### Quarterly (SOP-MOT-M02)
1. All monthly items plus:
2. Insulation resistance test (Megger)
   - 5 kV motors: 5000V test, > 100 MΩ
   - 6.6 kV motors: 5000V test, > 100 MΩ
3. Polarization index test (if IR < 500 MΩ)
4. Bearing lubrication
   - Per manufacturer specification
   - Record grease type and quantity
5. Alignment check
   - Laser alignment if vibration elevated

### Annually (SOP-MOT-M03)
1. All quarterly items plus:
2. Motor current signature analysis (MCSA)
3. Partial discharge testing (MV motors)
4. Thermal imaging
5. Terminal box inspection
   - Clean, tighten connections
   - Check for overheating signs
6. Air gap measurement (critical motors)

## Alarm Response Procedures

### High Bearing Temperature (ALM-MOT-HBT)
**Trigger**: Bearing temp > 85°C (DE), > 80°C (NDE)
**Immediate Actions**:
1. Verify with handheld thermometer
2. Check lubrication condition
3. Verify cooling fan operation
4. Check coupling alignment
5. If > 95°C, plan controlled shutdown

**Root Causes**:
- Over/under lubrication
- Wrong grease type
- Bearing wear
- Misalignment
- Cooling fan failure
- Overloading

### High Vibration (ALM-MOT-HVIB)
**Trigger**: Overall vibration > 4.5 mm/s (alarm), > 7 mm/s (trip)
**Immediate Actions**:
1. Take spectral reading
2. Check for loose bolts
3. Verify alignment
4. Check for soft foot
5. If 1x RPM dominant → unbalance
6. If 2x RPM dominant → misalignment
7. If bearing frequencies → bearing defect

### High Motor Current (ALM-MOT-HI)
**Trigger**: Current > 110% FLA
**Immediate Actions**:
1. Verify load hasn't increased
2. Check voltage balance
3. Check power factor
4. Verify driven equipment condition
5. Check for single phasing

## Troubleshooting Common Issues

### Recurring Bearing Failures
1. Check lubrication program compliance
2. Verify grease compatibility
3. Check shaft grounding (VFD motors)
4. Verify bearing fit tolerances
5. Check for circulating currents

### Recurring High Vibration
1. Perform full vibration analysis
2. Check alignment history
3. Verify foundation condition
4. Check for resonance
5. Inspect coupling condition

### Insulation Degradation
1. Trend IR and PI values
2. Check for moisture ingress
3. Verify space heaters operational
4. Check for contamination
5. Consider rewind if PI < 1.5

## Spare Parts Strategy
| Motor Rating | Critical Spares | Stock Level |
|--------------|-----------------|-------------|
| > 1 MW (MV) | DE/NDE bearings, RTDs, space heaters | 1 set each |
| 500 kW - 1 MV | DE/NDE bearings, RTDs | 1 set each |
| < 500 kV (LV) | Bearings (common sizes) | 2 sets |

## Safety
- LOTO required for all maintenance
- Verify zero energy state
- MV motors: arc flash PPE required
- Confined space entry for internal inspection