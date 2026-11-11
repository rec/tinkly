"""Build tinkly's documentation locally without publishing it."""

import tyro
from check_docs import check_pages
from reccy.documentation import Documentation

if __name__ == '__main__':
    index = tyro.cli(Documentation).build()
    count = check_pages(index)
    print(f'Checked {count} documentation pages: {index}')
