For spiritgui.py:
1. Per-tab, per-component visibility settings (show/hide)
2. Per-tab, per-component live-plotting options/settings
3. Per-component P&ID symbols

For DAQ scripts (or both):
1. Figure out how DAQ digital outputs should be written to. (Right now, if a digital-output task is added to SpiritGui, it can only cleanly handle being written to via SpiritGui's switches => no continuous digital patterns/signals can be written to that task.)
2. Consider LPF beforehand, when displaying downsampled data on the GUI (to prevent aliasing)
3. Extend example_tc_ai_valve_do.py for >1 AI tasks
4. Standardize SPIRIT's DAQ scripts
5. Per-channel logging option (enables capturing data with better time resolution compared to what is seen from the gui)
6. Create a separate file (like channels.toml) for configuration variables (such as AI_TASK_0_PHYSICAL_CHANNELS, AI_TASK_0_CHANNEL_UNITS, DO_TASK_0_START_STATES, ...) for more organized code
7. If logging functionality is added to DAQ scripts, you could save the data/outputs in a folder called 'runs' (see .gitignore)

Note: make sure to read about the limitations of the specific DAQ and modules you're using.