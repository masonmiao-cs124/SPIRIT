import time
import nidaqmx
from nidaqmx.constants import (
    ThermocoupleType,
    CJCSource,
    ADCTimingMode,
    AcquisitionType,
)
import matplotlib.pyplot as plt

DEVICE_CHANNEL = "cDAQ1Mod1/ai0"
SAMPLE_RATE = 2.0
TOTAL_SECONDS = 30

times = []
temperatures = []

with nidaqmx.Task() as task:
    channel = task.ai_channels.add_ai_thrmcpl_chan(
        DEVICE_CHANNEL,
        thermocouple_type=ThermocoupleType.T,
        cjc_source=CJCSource.BUILT_IN,
    )

    # Faster conversion, with less filtering/noise rejection.
    channel.ai_adc_timing_mode = ADCTimingMode.HIGH_SPEED

    # Configure actual hardware-timed sampling.
    task.timing.cfg_samp_clk_timing(
        rate=SAMPLE_RATE,
        sample_mode=AcquisitionType.CONTINUOUS,
        samps_per_chan=10,
    )

    print(f"Starting acquisition at {SAMPLE_RATE} samples/second...")
    task.start()
    start_time = time.perf_counter()

    try:
        while time.perf_counter() - start_time < TOTAL_SECONDS:
            # No time.sleep(): this blocks until the next hardware sample.
            temperature = task.read(
                number_of_samples_per_channel=1,
                timeout=2.0,
            )[0]

            elapsed = time.perf_counter() - start_time
            times.append(elapsed)
            temperatures.append(temperature)

            print(
                f"Time: {elapsed:.1f}s | "
                f"Temperature: {temperature:.2f} °C"
            )

    except KeyboardInterrupt:
        print("\nAcquisition stopped manually.")

plt.plot(times, temperatures, marker="o")
plt.title("NI-9213 Thermocouple Measurements")
plt.xlabel("Time (seconds)")
plt.ylabel("Temperature (°C)")
plt.grid(True)
plt.tight_layout()
plt.show()