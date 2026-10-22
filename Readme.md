# Pi-kilo

A prototype integration of the Pi coding agent with Kilo’s shared project/session experience, so a user can move between Pi, Kilo CLI, and Kilo Cloud without losing work continuity.

The desired experience is for `app.kilo.ai` not caring which compatible runtime is executing a session. The interface shows shared conversation, and messages should reach whichever runtime currently owns execution.

This is runtime interoperability, not merely exporting a transcript or displaying a read-only copy of another agent’s session.
