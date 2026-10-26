# Settings/NVS preservation regression gate

Run `python3 tests/subsys/settings/nvs_preservation/test_host.py` from the fork.
The script extracts complete production functions from settings_nvs.c,
settings_store.c and settings.c, compiles them with host NVS/handler doubles,
and runs the matrix with the name cache disabled and enabled. Temporary outputs
are scoped to TemporaryDirectory. No device is accessed.

The approved base is c425eabae5724d39fdd828d31ec35dc850795fe1.
The AirFoot original reproducer at that base reports:

```
production NVS loader: injected value read -EIO -> 2 deletes, 1 metadata writes, result 0
production subtree loader: injected backend -EIO -> result 0
```

The patch chooses read-only loading: incomplete pairs are skipped, never cleaned
or renumbered on load. This also preserves orphan records for later recovery.
It can retain occupied orphan space until an explicit save/delete; it does not
promise to reclaim every incomplete record in a full store. No partition geometry,
record IDs, name/value encoding, public struct or preset/Bluetooth schema changes.
Load is not a RAM transaction: handlers already called before a later error may
have updated RAM. Failed loads do not invoke the Settings commit phase. Callers
must honor the returned error and must not save defaults following a failed load.

Coverage: name/value probe EIO, late EIO after a missing pair, empty/oversized/
embedded-NUL names, zero values, callback EIO and short reads even if the handler
swallows them, incomplete pairs, metadata ENOENT/EIO/short/invalid IDs, handler
EIO and forward-compatible ENOENT, cache lookup EIO, healthy read/save/delete,
ENOSPC propagation, subtree/direct backend errors, lock release and no commit.
Read faults assert zero deletes/writes and unchanged last_name_id. Healthy load
also checks synthetic records byte-for-byte. These are logical legacy-format
fixtures, not physical flash images or production Bluetooth handler integration.
NVS returns the stored record length even when the request buffer is shorter;
a one-byte value probe returning a larger length is expected, not a short read.

Release gates still pending: Linux Zephyr static/dynamic Settings and Bluetooth
integration suites, representative archived preset/identity/bond flash images,
rollback compatibility, read-only physical backup, and authorized HIL/power-loss
validation. macOS native_sim configuration fails because POSIX requires Linux.
Do not adopt this fork or flash hardware based only on this host test.
