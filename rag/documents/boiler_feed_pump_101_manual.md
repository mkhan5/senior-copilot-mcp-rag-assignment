# Boiler Feed Pump 101 - Operating Manual

## Equipment Overview
- **Asset ID**: BFP-101
- **Asset Name**: Boiler Feed Pump 101
- **Manufacturer**: ABB
- **Model**: BFP-5000-HP
- **Serial Number**: SN-BFP-101-4821
- **Install Date**: 2020-01-15
- **Location**: Unit 1, NorthPlant
- **Criticality**: High

## Technical Specifications
- **Flow Rate**: 500 m³/hr
- **Discharge Pressure**: 150 bar
- **Suction Pressure**: 5 bar
- **Motor Rating**: 2.5 MW, 6.6 kV
- **Speed**: 3000 RPM
- **NPSH Required**: 8 m

## Normal Operating Parameters
| Parameter | Normal Range | Alarm Low | Alarm High | Trip Low | Trip High |
|-----------|-------------|-----------|------------|----------|-----------|
| Suction Pressure | 4-6 bar | 3.5 bar | 7 bar | 3 bar | 8 bar |
| Discharge Pressure | 140-155 bar | 130 bar | 165 bar | 120 bar | 180 bar |
| Flow Rate | 450-550 m³/hr | 400 m³/hr | 600 m³/hr | 350 m³/hr | 650 m³/hr |
| Bearing Temp (DE) | 50-70°C | - | 80°C | - | 95°C |
| Bearing Temp (NDE) | 50-70°C | - | 80°C | - | 95°C |
| Vibration (DE) | 0-2.5 mm/s | - | 4.5 mm/s | - | 7 mm/s |
| Vibration (NDE) | 0-2.5 mm/s | - | 4.5 mm/s | - | 7 mm/s |
| Motor Current | 180-220 A | - | 250 A | - | 300 A |

## Alarm Response Procedures

### High Discharge Pressure Alarm (ALM-HDP)
**Trigger**: Discharge pressure > 165 bar
**Immediate Actions**:
1. Verify pressure reading on local gauge
2. Check discharge valve position - ensure fully open
3. Check for discharge line blockage
4. Verify boiler feedwater demand has not suddenly dropped
5. If pressure continues rising, initiate controlled shutdown per procedure SOP-BFP-003

**Root Cause Analysis**:
- Discharge valve partially closed
- Boiler load rejection
- Control valve malfunction
- Instrument error

### Low Suction Pressure Alarm (ALM-LSP)
**Trigger**: Suction pressure < 3.5 bar
**Immediate Actions**:
1. Verify deaerator level > 50%
2. Check suction strainer differential pressure
3. Verify condensate pump operation
4. Check for air ingress in suction line
5. If NPSH margin inadequate, reduce pump speed

**Root Cause Analysis**:
- Deaerator low level
- Suction strainer clogged
- Condensate pump trip
- Air leakage in suction piping

### High Bearing Temperature Alarm (ALM-HBT)
**Trigger**: Bearing temperature > 80°C
**Immediate Actions**:
1. Verify oil level in bearing housing
2. Check oil cooler operation
3. Verify bearing vibration readings
4. Check for unusual noise
5. If temperature > 90°C, prepare for emergency shutdown

**Root Cause Analysis**:
- Insufficient lubrication
- Oil cooler fouling
- Bearing wear/damage
- Misalignment
- Overloading

### High Vibration Alarm (ALM-HVIB)
**Trigger**: Vibration > 4.5 mm/s
**Immediate Actions**:
1. Compare with historical trend
2. Check for loose foundation bolts
3. Verify coupling alignment
4. Check for cavitation signs
5. If vibration > 7 mm/s, trip immediately

**Root Cause Analysis**:
- Misalignment
- Unbalance
- Bearing defects
- Cavitation
- Foundation issues
- Resonance

## Startup Procedure (SOP-BFP-001)
1. Verify all isolation valves open
2. Confirm deaerator level > 70%
3. Start oil lubrication system, verify pressure > 2 bar
4. Perform turning gear operation for 10 minutes
5. Start condensate booster pumps
6. Slowly open suction valve
7. Start pump motor
8. Verify discharge pressure builds to > 100 bar
9. Slowly open discharge valve
10. Ramp to operating speed
11. Verify all parameters within normal range

## Shutdown Procedure (SOP-BFP-002)
1. Gradually reduce load
2. Close discharge valve
3. Stop motor
4. Keep oil lubrication running for 30 minutes
5. Close suction valve
6. Drain pump if extended outage

## Emergency Shutdown (SOP-BFP-003)
**Conditions**: Any trip condition met or unsafe operation
1. Press emergency stop button
2. Verify pump stops
3. Close suction and discharge valves
4. Isolate electrical supply
5. Notify control room
6. Log all parameters at time of trip

## Maintenance Schedule
| Activity | Frequency | Procedure |
|----------|-----------|-----------|
| Visual inspection | Daily | SOP-BFP-M01 |
| Bearing temperature check | Shift | SOP-BFP-M02 |
| Vibration monitoring | Continuous | SOP-BFP-M03 |
| Oil analysis | Monthly | SOP-BFP-M04 |
| Alignment check | Quarterly | SOP-BFP-M05 |
| Bearing replacement | 24 months | SOP-BFP-M06 |
| Mechanical seal inspection | 12 months | SOP-BFP-M07 |
| Performance test | 6 months | SOP-BFP-M08 |

## Troubleshooting Guide

### Recurring High Pressure Alarms
If high discharge pressure alarms recur:
1. Check control valve calibration
2. Verify boiler load stability
3. Inspect discharge check valve
4. Review pressure transmitter calibration
5. Consider control loop tuning

### Recurring Low Suction Pressure
If low suction pressure alarms recur:
1. Inspect suction strainers weekly
2. Verify deaerator level control
3. Check condensate pump performance curves
4. Inspect suction piping for air leaks
5. Consider NPSH margin improvement

### Recurring High Vibration
If high vibration alarms recur:
1. Perform detailed vibration analysis (FFT)
2. Check alignment history
3. Inspect foundation and grout
4. Verify balancing of rotating elements
5. Check for process-induced vibration

## Spare Parts List (Critical)
| Part Number | Description | Min Stock | Lead Time |
|-------------|-------------|-----------|-----------|
| PN-BFP-101-001 | Mechanical Seal Kit | 1 | 4 weeks |
| PN-BFP-101-002 | DE Bearing (SKF 7315 BECBM) | 1 | 2 weeks |
| PN-BFP-101-003 | NDE Bearing (SKF 6314 C3) | 1 | 2 weeks |
| PN-BFP-101-004 | Oil Cooler Bundle | 1 | 6 weeks |
| PN-BFP-101-005 | Coupling Element Set | 2 | 1 week |
| PN-BFP-101-006 | Suction Strainer Element | 2 | 1 week |

## Safety Notes
- Always follow lockout/tagout procedure before maintenance
- High pressure fluid hazard - depressurize before breaking containment
- Electrical hazard - 6.6 kV motor, verify isolation
- Rotating machinery - verify zero speed before approach
- Hot surfaces - bearing housings can exceed 80°C