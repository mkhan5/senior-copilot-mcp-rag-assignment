# Compressor 201 - Operating Manual

## Equipment Overview
- **Asset ID**: COMP-201
- **Asset Name**: Compressor 201
- **Manufacturer**: ABB
- **Model**: COMP-3000-CENT
- **Serial Number**: SN-COMP-201-3192
- **Install Date**: 2019-06-20
- **Location**: Unit 2, NorthPlant
- **Criticality**: High

## Technical Specifications
- **Type**: Centrifugal Compressor
- **Flow Rate**: 10,000 Nm³/hr
- **Discharge Pressure**: 40 bar
- **Suction Pressure**: 1.2 bar
- **Motor Rating**: 1.8 MW, 6.6 kV
- **Speed**: 10,500 RPM
- **Stages**: 3

## Normal Operating Parameters
| Parameter | Normal Range | Alarm Low | Alarm High | Trip Low | Trip High |
|-----------|-------------|-----------|------------|----------|-----------|
| Suction Pressure | 1.0-1.4 bar | 0.8 bar | 1.6 bar | 0.6 bar | 1.8 bar |
| Discharge Pressure | 35-42 bar | 30 bar | 45 bar | 25 bar | 50 bar |
| Flow Rate | 9000-11000 Nm³/hr | 8000 | 12000 | 7000 | 13000 |
| Lube Oil Pressure | 2.5-3.5 bar | 2.0 bar | 4.0 bar | 1.5 bar | 4.5 bar |
| Lube Oil Temp | 40-55°C | - | 65°C | - | 75°C |
| Vibration (X) | 0-20 µm | - | 40 µm | - | 60 µm |
| Vibration (Y) | 0-20 µm | - | 40 µm | - | 60 µm |
| Seal Gas Pressure | 5-6 bar | 4 bar | 7 bar | 3.5 bar | 8 bar |

## Alarm Response Procedures

### Surge Alarm (ALM-SURGE)
**Trigger**: Flow drops below surge control line
**Immediate Actions**:
1. Verify anti-surge valve opening
2. Check suction throttle valve position
3. Increase recycle flow
4. If surge persists, trip compressor per SOP-COMP-003

**Root Cause Analysis**:
- Process demand drop
- Anti-surge valve failure
- Suction throttle malfunction
- Control system error

### High Discharge Temperature (ALM-HDT)
**Trigger**: Discharge temperature > 150°C
**Immediate Actions**:
1. Check intercooler performance
2. Verify cooling water flow
3. Check for internal leakage
4. Reduce load if possible

**Root Cause Analysis**:
- Intercooler fouling
- Cooling water loss
- Internal recirculation
- Excessive pressure ratio

### Low Lube Oil Pressure (ALM-LLOP)
**Trigger**: Lube oil pressure < 2.0 bar
**Immediate Actions**:
1. Verify lube oil pump running
2. Check oil level in reservoir
3. Check filter differential pressure
4. If pressure < 1.5 bar, trip immediately

**Root Cause Analysis**:
- Lube oil pump failure
- Low oil level
- Filter blockage
- Bearing wear

## Maintenance Procedures

### Daily Inspection (SOP-COMP-M01)
1. Check lube oil level and pressure
2. Verify cooling water flows
3. Check vibration readings
4. Inspect for leaks
5. Log all parameters

### Monthly Maintenance (SOP-COMP-M02)
1. Clean/replace air intake filters
2. Check coupling alignment
3. Verify safety valve operation
4. Test anti-surge control
5. Oil analysis

### Quarterly Maintenance (SOP-COMP-M03)
1. Internal inspection (borescope)
2. Bearing inspection
3. Seal inspection
4. Vibration analysis (full spectrum)
5. Performance test

## Troubleshooting

### Recurring Surge Alarms
1. Verify anti-surge controller tuning
2. Check suction valve response time
3. Review process demand profile
4. Consider wider control margin

### Recurring High Vibration
1. Perform FFT analysis
2. Check for rotor rub
3. Verify bearing clearances
4. Check foundation integrity