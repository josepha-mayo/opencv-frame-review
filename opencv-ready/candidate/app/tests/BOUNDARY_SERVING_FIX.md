# Static boundary serving corrections

Independent source review on 16 October 2026 found a deterministic integrity race in the initial staged feature. The image route first validated PNG hashes through Manager.frame_review, then reopened the requested PNG through Handler.file. Replacing frame 0 with a different valid frame 1 PNG between these steps yielded 200 with bytes that did not match the recorded hash. The initial 11 tests did not catch this. This was a tiny owned synthetic-file reproduction, not an attack against a deployed service.

The correction serves the exact buffer whose digest is checked. The manifest is also read once, verified and parsed from that same buffer. The added regression swaps the PNG immediately after initial validation and requires 400. Another test changes the manifest on disk after the read and verifies that the parsed object comes solely from the hashed buffer; the next request refuses the changed file.

A second review found that the initial validation still used an unbounded image read and a read-only open could block on a substituted FIFO before checking file type. One shared reader now uses no-follow/nonblocking open, checks regular-file status and the size cap, then reads at most limit+1 bytes. The manifest cap is 1 MiB; each PNG cap is 4 MiB. Both validation and serving use this reader. Tests exercise an oversized sparse file, FIFO and symlink using temporary owned files.

These corrections cover the new artifact path. They are not a malicious-media certification or a broad local-filesystem security guarantee. Existing full-video upload/parser limits and release caveats still apply. No video processing or cloud change was used to reproduce or fix these serving issues.
