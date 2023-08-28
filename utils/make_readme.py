""" Make readme with links to cards.

Using a template, add a list of linked entries for each output card.None
Read the card for a README: comment; if it exists, use it as an explanation
link.
"""

import itertools
import re
import subprocess
from argparse import ArgumentParser, Namespace, RawTextHelpFormatter
from enum import Enum
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
TEMPLATE = PROJECT_DIR / '.README.tmpl.md'
OUTPUT = PROJECT_DIR / 'AUTOREADME.md'


class BuildFiles:
    """Check and report, or make missing cards.

    Go through src and find all .tex files.  Check and ensure there is a
    pdf file in out (with date equal or later to check-in date?  That might be
    difficult).

    Depending on the option selected:
     - no - do nothing (ignore checks)
     - check - just report
     - missing - make missing pdfs
     - all - rebuild all pdfs even if they exist (warning, will reset the date
             on the bottom of the card)
    """

    Option = Enum('Option', ['NOTHING', 'CHECK', 'MISSING', 'ALL'])
    OPTIONS_NOTHING = ['no', 'n', ]
    OPTIONS_CHECK = ['check-only', 'check', 'c', ]
    OPTIONS_MISSING = ['build-missing', 'missing', 'm', ]
    OPTIONS_ALL = ['build-all', 'all', 'a', ]

    def __init__(self, build: str):

        def _parse_build_arg():
            """use a consistent argument.

            The parser allows long, short, and one-character values.
            parse them all to a consistent value.
            """
            if build in self.OPTIONS_NOTHING:
                return self.Option.NOTHING
            elif build in self.OPTIONS_CHECK:
                return self.Option.CHECK
            elif build in self.OPTIONS_MISSING:
                return self.Option.MISSING
            elif build in self.OPTIONS_ALL:
                return self.Option.ALL
            raise ValueError(f'Unknown option {build}')

        super().__init__()
        self.build = _parse_build_arg()

    @staticmethod
    def _check_missing() -> list[Path]:
        """Return a list of .tex files in src with no .pdf in out.

        Note this is stupid. It just checks for existence, not whether
        it is up to date or even a PDF file.

        TODO: we can check PDF if we install pypdf4.

        """
        missing = []
        for file in (PROJECT_DIR / 'src').glob('*.tex'):
            if not (PROJECT_DIR / 'out' / f"{file.stem}.pdf").exists():
                missing.append(file)
        return missing

    @staticmethod
    def _build_file(tex_file: Path) -> None:
        """Build the file (twice, just in case)."""
        for _ in range(2):
            try:
                subprocess.run(
                    ['pdflatex',
                     '-halt-on-error',
                     '-output-directory',
                     f'{PROJECT_DIR}/out',
                     tex_file, ],
                    capture_output=True,
                    check=True,
                )
            except subprocess.CalledProcessError as e:
                print("Build FAILED!")
                print(f"stdout:\n{e.stdout.decode()}")
                print(f"\nstderr:\n{e.stderr.decode()}")
                raise

    @staticmethod
    def _do_build_nothing() -> None:
        print('No build check requested')

    def _do_build_check(self) -> None:
        for missing in self._check_missing():
            print(f"Missing PDF: {missing.stem}.pdf")

    def _do_build_missing(self) -> None:
        for missing in self._check_missing():
            print('Building missing PDF file: '
                  f"{missing.with_suffix('.pdf').name}")
            self._build_file(missing)

    def _do_build_all(self) -> None:
        print(f"Building all files in {PROJECT_DIR}/src!")
        for f in (PROJECT_DIR / 'src').glob('*.tex'):
            print(f"Building: {f.with_suffix('.pdf').name}")
            self._build_file(f)

    def do_build(self) -> None:
        """DTRT based on request"""
        getattr(self, f'_do_build_{self.build.name.lower()}')()


class MakeReadme:

    def __init__(self, template=TEMPLATE):
        super().__init__()
        self.template = Path(template)

    @staticmethod
    def _make_list() -> str:
        cardlist = []
        pattern = re.compile('README: \[([^]]*)]')
        for f in Path(PROJECT_DIR / 'out').glob('*.pdf'):
            comment = f"{f.stem} card"
            src = f.parent.parent / 'src' / f"{f.stem}.tex"
            try:
                fulltext = src.read_text()
                match = pattern.search(fulltext)
                if match is not None:
                    comment = match[1]
            except FileNotFoundError:
                print(f"WARNING: could not find source {src} for card {f}")
            cardlist.append(f"- [{f.stem}](out/{f.name}): {comment}")

        return '\n'.join(sorted(cardlist, key=str.casefold))

    def make_readme(self) -> None:
        """Build readme from template, output to README.md"""

        tmpl = self.template.read_text()
        # put all the replacement stuff here
        tmpl = tmpl.replace('[cardlist]', self._make_list())
        OUTPUT.write_text(tmpl)


def parse_args() -> Namespace:
    parser = ArgumentParser(description='Build README file from made cards,'
                            'and check for unbuilt cards.',
                            formatter_class=RawTextHelpFormatter)
    parser.add_argument(
        '--template', '-t',
        default=TEMPLATE,
        help=f'The template file.  Default is {TEMPLATE}'
    )
    output_choices = (itertools.chain(BuildFiles.OPTIONS_NOTHING,
                              BuildFiles.OPTIONS_CHECK,
                              BuildFiles.OPTIONS_MISSING,
                              BuildFiles.OPTIONS_ALL))
    parser.add_argument(
        '--build_output', '-o',
        choices=output_choices,
        default='check-only',
        help=('what to do with missing output files.Options: \n'
              '    No, Check-only, build-Missing, build-All.\nCan abbreviate '
              'to capitalized letter or word'),
        metavar='{options}'
    )
    return parser.parse_args()


def main():
    args = parse_args()
    BuildFiles(args.build_output).do_build()
    readme = MakeReadme(args.template)
    readme.make_readme()


if __name__ == '__main__':
    main()
