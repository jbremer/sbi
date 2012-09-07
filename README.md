sbi
===

Static Binary Instrumentation: Rewrite binaries.

SBI is a static variant of the well-known Dynamic Binary Instrumentation
frameworks. Static Binary Instrumentation is a tool to aid in static analysis
without depending on a particular tool (different tools exist for different
binary types, such as x86, java, .NET, etc.)

Using SBI one can write semi-generic scripts to alter the contents for
different types of binaries. Therefore, SBI allows one to remove obfuscations
etc enforced to make Reverse Engineering a harder task, resulting in a binary
which can be Reverse Engineered in a normal way by regular tools.

Whereas existing DBI frameworks are limited to certain architectures and
platforms, an SBI framework can do about any kind of binary, because there is
no need to run the binary itself.

That being said, Static Binary Instrumentation offers an easy to use API to
manipulate existing binaries.

For questions, bugs, or to contribute, please make a pull request or join us
on the official irc channel #sbi on freenode.
