"""APEX_GEN5 scheduler package (S9.5-14 scheduler law; Ch.23 execution model
L18253-18260; AI.7 clock drift/NTP L18722-18725).

Normative tree file (S9.5-10): ``apex/scheduler/clock.py`` -- the fixture/real
clock, the 140-cell (Core-10 x 14 TF) close schedule, the P0-P3 stage order,
the bounded worker pool (semaphore 4) and the drift block.
"""
