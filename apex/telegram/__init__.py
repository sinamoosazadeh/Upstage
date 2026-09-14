"""APEX_GEN5 Telegram package (Ch.21 Telegram Control and Signaling
L17562-18220; Ch.23 Monitoring and Alert Policy L18290-18314).

Normative tree files (S9.5-10): ``apex/telegram/control_plane.py`` (screens,
callbacks, roles, busy guard, emergency ladder) and
``apex/telegram/signaling.py`` (outbound P0-P3 tier, alert policy, token
bucket, retry, idempotency, Agg-only in-memory charts).

Telegram is a downstream control/reporting interface: it never becomes market
truth, portfolio truth, or Risk authority, and signaling failure NEVER blocks
protective execution (Ch.21 S1 L17570-17578, L18007).
"""
