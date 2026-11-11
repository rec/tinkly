"""Build tinkly's documentation locally without publishing it."""

import tyro
from reccy.documentation import Documentation

if __name__ == '__main__':
    print(tyro.cli(Documentation).build())
