"""LCD mini-games and tools for the Cazio arcade.

Everything in this package is pure Python (no Qt imports): games draw into a
:class:`games.base.PixelGrid` and the Qt layer simply paints that grid as LCD
dots. That keeps the games unit-testable on a headless CI machine.
"""
