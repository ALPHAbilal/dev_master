# generators / yield

A function containing `yield` is a **pause button**. Calling it runs none of the
body — it hands back a generator object frozen at the top. Each time a `for` loop
asks for the next item, the body runs until the next `yield`, hands that value to
the loop (it becomes the loop variable), then **freezes on the yield line**. The
next request resumes on the line *after* yield.

Why the pipeline needs it: `stream_records` yields one JSON record at a time, so a
2.3 GB file never enters memory whole — only one record sits in RAM at once.

Bilal's path: overwhelmed by `yield n` cold. Went to floor — plain `print`
countdown (HIT), swapped print->yield, built the "hand to whoever loops over me"
wire, then in his OWN words: "it stops in the handing, n=n-1 isn't executed yet,
but when asking again it continues, pause and resume." Transfer test (interleaved
A/10/B/20/C generator) predicted exactly right — ordering only obtainable from the
pause model. CAN, copy-checked on a new instance.
