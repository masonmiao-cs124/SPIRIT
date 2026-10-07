# SPIRIT Electrical and Data Acquisition

This repository supports the electrical, instrumentation, control, and data-acquisition work for the **Subscale Propulsion Integration, Research, and Instruction Testbed (SPIRIT)** at the University of Illinois Urbana-Champaign.

SPIRIT is a modular rocket-propulsion test facility intended to support research, instruction, and student projects involving solid, hybrid, and liquid engines. The current design effort focuses on a **10 kN testbed** that will serve as a proof of concept for larger test infrastructure.

## Electrical team scope

The electrical team is responsible for the systems that connect the test article, fluid system, safety hardware, and control room:

- Sensor selection, excitation, signal conditioning, and calibration
- Data-acquisition hardware and channel allocation
- Solenoid-valve actuation through isolated power and relay interfaces
- Test sequencing, live monitoring, and data recording
- Emergency-stop and facility-safety signal integration

## System architecture

The preliminary design uses a modular **National Instruments CompactDAQ** platform. The selected concept provides analog inputs for pressure, thrust, and safety instrumentation; cold-junction-compensated thermocouple inputs; and digital outputs for valve control. A spare chassis module allows future expansion.

The modules include:
- NI 9213 16 input Thermocouple Module
- NI 9205 32 input Analog Voltage Module
- NI 9476 32 output Digital Output Module

## Preliminary I/O baseline

| Function | Current baseline |
| --- | --- |
| Analog input capacity | 32 channels |
| Estimated analog inputs | 21 channels |
| Thermocouple capacity | 16 channels with cold-junction compensation |
| Estimated digital outputs| 10 channels |
| Digital output capacity | 32 channels |
| Fluid-system instrumentation | 12 pressure transducers and 6 thermocouples |
| Test-article instrumentation | Load cell, 8 thermocouples, accelerometer, and pressure transducers |

The DAQ must capture synchronized thrust, pressure, temperature, mass-flow, valve-state, and safety data at rates appropriate for each measurement. The control software will store reusable channel configurations, sensor scaling, calibration data, and test definitions.

### Pressure measurement

The fluid-system pressure-transducer baseline calls for:

- 3,000 psi rating
- Voltage output with a 1 ms response time
- 316 stainless-steel wetted construction
- Oxygen-clean compatibility for oxidizer service
- Operating temperature from -40 °C to 85 °C
- Isolated 9–36 V excitation

Thermal standoffs will protect transducers near cryogenic plumbing. The current estimate uses an approximately 3 in standoff, subject to final thermal and installation analysis.

### Temperature measurement

Type T thermocouples provide the required cryogenic range. The current candidate is rated from -200 °C to 260 °C and connects to a dedicated cold-junction-compensated module.

### Thrust measurement

The thrust channel uses a compression load cell and bridge measurement. The final sensor must support the 5 kN engine class, provide suitable overload margin, and meet the required accuracy at both nominal and lower thrust levels. Excitation, bridge completion, and off-axis-load performance still require validation before the design is frozen.

### Valve actuation

The DAQ commands fluid-system solenoids through a relay interface. The valves use an independent, isolated 24 V supply because the DAQ cannot provide the required actuator current. The preliminary firing case assumes up to four general-purpose valves and four smaller valves operating simultaneously, for an estimated peak draw of 4.8 A.

## Safety integration

TBD

## Repository goals

As the design continues through the semester, this repository will contain:

- Electrical architecture and interface documentation
- I/O maps and wiring definitions
- Sensor specifications and calibration records
- DAQ and control software
- Reusable test configurations
- Verification plans and test results
- Reviewed operating and safety documentation

