import time
import nidaqmx
from nidaqmx.constants import (
    ThermocoupleType,
    CJCSource,
    ADCTimingMode,
    AcquisitionType,
)
import matplotlib.pyplot as plt

DEVICE_CHANNELS = "cDAQ2Mod1/ai0, cDAQ2Mod1/ai1"  # ai0 and ai2
CHANNEL_LABELS = ["ai0", "ai1"]
SAMPLE_RATE = 2.0
TOTAL_SECONDS = 30

times = []
temperatures = {label: [] for label in CHANNEL_LABELS}

with nidaqmx.Task() as task:
    channels = task.ai_channels.add_ai_thrmcpl_chan(
        DEVICE_CHANNELS,
        thermocouple_type=ThermocoupleType.T,
        cjc_source=CJCSource.BUILT_IN,
    )

    # Faster conversion, with less filtering/noise rejection.
    # Applies to both channels (the NI-9213 shares one ADC across channels).
    channels.ai_adc_timing_mode = ADCTimingMode.HIGH_SPEED

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
            # With two channels, read() returns [[ai0_value], [ai2_value]].
            sample = task.read(
                number_of_samples_per_channel=1,
                timeout=2.0,
            )
            readings = [channel_data[0] for channel_data in sample]

            elapsed = time.perf_counter() - start_time
            times.append(elapsed)
            for label, temperature in zip(CHANNEL_LABELS, readings):
                temperatures[label].append(temperature)

            print(
                f"Time: {elapsed:.1f}s | "
                + " | ".join(
                    f"{label}: {temperature:.2f} °C"
                    for label, temperature in zip(CHANNEL_LABELS, readings)
                )
            )

    except KeyboardInterrupt:
        print("\nAcquisition stopped manually.")

for label in CHANNEL_LABELS:
    plt.plot(times, temperatures[label], marker="o", label=label)
plt.title("NI-9213 Thermocouple Measurements (cDAQ2Mod1)")
plt.xlabel("Time (seconds)")
plt.ylabel("Temperature (°C)")
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.show()