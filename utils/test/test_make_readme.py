import contextlib
import io
import shutil
from subprocess import CalledProcessError
import unittest
from pathlib import Path
from unittest.mock import call, patch

from utils import make_readme as mr


FAKE_PROJECT_DIR = Path(__file__).resolve().parent / 'data'


class TestMain(unittest.TestCase):

    def test_parser_default(self):
        """parser default values"""
        with patch('sys.argv', ['make_readme.py']):
            args = mr.parse_args()
        self.assertEqual(set(vars(args).keys()),
                         {'build_output', 'template'})
        self.assertEqual(args.build_output, 'check-only')
        self.assertEqual(args.template, mr.TEMPLATE)

    @patch('utils.make_readme.BuildFiles', spec=True)
    @patch('utils.make_readme.MakeReadme', spec=True)
    def test_main(self, mock_make_readme, mock_build_files):
        """Check calls to everything"""
        mr.main()
        mock_build_files.assert_called()
        self.assertIn(call().do_build(), mock_build_files.mock_calls)
        mock_make_readme.assert_called()
        self.assertIn(call().make_readme(), mock_make_readme.mock_calls)


class TestBuild(unittest.TestCase):
    PATCH_CLASS = 'utils.make_readme.BuildFiles'
    CHECK_MISSING = f'{PATCH_CLASS}._check_missing'
    BUILD_FILE = f'{PATCH_CLASS}._build_file'

    def setUp(self) -> None:
        self.files_to_delete = []
        self.patch_project_dir = patch('utils.make_readme.PROJECT_DIR',
                                       FAKE_PROJECT_DIR)

    def test_parse_build_option(self):
        """Ensure consistent build values"""
        for option in mr.BuildFiles.OPTIONS_NOTHING:
            b = mr.BuildFiles(option)
            self.assertEqual(b.build, mr.BuildFiles.Option.NOTHING)
        for option in mr.BuildFiles.OPTIONS_CHECK:
            b = mr.BuildFiles(option)
            self.assertEqual(b.build, mr.BuildFiles.Option.CHECK)
        for option in mr.BuildFiles.OPTIONS_MISSING:
            b = mr.BuildFiles(option)
            self.assertEqual(b.build, mr.BuildFiles.Option.MISSING)
        for option in mr.BuildFiles.OPTIONS_ALL:
            b = mr.BuildFiles(option)
            self.assertEqual(b.build, mr.BuildFiles.Option.ALL)

    @patch(BUILD_FILE)
    @patch(CHECK_MISSING)
    def test_build_nothing(self, check_missing, build_file):
        """Ensure build option nothing does nothing"""
        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            mr.BuildFiles('n').do_build()
        self.assertIn('build check', f.getvalue())
        check_missing.assert_not_called()
        build_file.assert_not_called()

    def test_build_check(self):
        """Ensure build option check returns correct missing files"""
        testfile = Path('test.tex')
        f = io.StringIO()
        with contextlib.redirect_stdout(f), \
                patch(self.CHECK_MISSING, return_value=[testfile]):
            mr.BuildFiles('c').do_build()
        output = f.getvalue()
        self.assertIn(str(testfile).replace('tex', 'pdf'), output)
        self.assertIn('Missing', output)

    @patch(BUILD_FILE)
    def test_build_missing(self, build_file):
        """Ensure build option missing builds the missing files"""
        testfile1 = Path('test1.tex')
        testfile2 = Path('test2.tex')
        f = io.StringIO()
        with contextlib.redirect_stdout(f), \
                patch(self.CHECK_MISSING, return_value=[testfile1, testfile2]):
            mr.BuildFiles('m').do_build()
        build_file.assert_any_call(testfile1)
        build_file.assert_any_call(testfile2)

    @patch(BUILD_FILE)
    def test_build_all(self, build_file):
        """Ensure build option all builds all files"""
        with self.patch_project_dir:
            mr.BuildFiles('a').do_build()
        for file in (FAKE_PROJECT_DIR / 'src').glob('*.tex'):
            build_file.assert_any_call(file)

    def test_check_missing(self):
        with self.patch_project_dir:
            missing = mr.BuildFiles('c')._check_missing()
        self.assertEqual([FAKE_PROJECT_DIR / 'src' / 'test2.tex'], missing)

    def test_build_file(self):
        source = FAKE_PROJECT_DIR / 'src' / 'test3.tex'
        dest = FAKE_PROJECT_DIR / 'out' / 'test3.pdf'
        # mark output and auxiliary files for cleanup
        self.files_to_delete.extend([
            dest.with_suffix('.aux'),
            dest.with_suffix('.log'),
        ])

        with self.patch_project_dir:
            mr.BuildFiles('m')._build_file(source)
        self.assertTrue(dest.exists())
        log = dest.with_suffix('.log').read_text()
        self.assertIn(f"Output written on {dest}",
                      log.replace('\n', ''))  # strip newlines

    def test_build_broken_file(self):
        source = FAKE_PROJECT_DIR / 'src' / 'test2.tex'
        dest = FAKE_PROJECT_DIR / 'out' / 'test2.pdf'
        # mark output and auxiliary files for cleanup
        self.files_to_delete.extend([
            dest,
            dest.with_suffix('.aux'),
            dest.with_suffix('.log'),
        ])

        with self.patch_project_dir, self.assertRaises(CalledProcessError):
            mr.BuildFiles('m')._build_file(source)
        log = dest.with_suffix('.log').read_text()
        self.assertIn('\\broken', log.replace('\n', ''))

    def tearDown(self) -> None:
        """Clean up"""
        for f in self.files_to_delete:
            f.unlink(missing_ok=True)


class TestMakeReadme(unittest.TestCase):
    README = Path(FAKE_PROJECT_DIR / 'README.md')

    def _delete_readme(self) -> None:
        self.README.unlink(missing_ok=True)

    def setUp(self) -> None:
        self._delete_readme()
        self.patch_readme = patch('utils.make_readme.OUTPUT', self.README)
        self.patch_project_dir = patch('utils.make_readme.PROJECT_DIR',
                                       FAKE_PROJECT_DIR)
        self.files_to_delete = []

    def test_build_list(self):
        """Test the _build_list function."""
        with self.patch_project_dir:
            cardtext = mr.MakeReadme()._make_list()
        cardlist = cardtext.split('\n')  # easier to evaluate as list of strings
        self.assertEqual(len(cardlist), 2)
        self.assertIn(f"- [test1](out/test1.pdf)", cardlist[0])
        self.assertIn('used only for tests', cardlist[0])
        self.assertIn(f"- [test3](out/test3.pdf)", cardlist[1])
        self.assertIn(f"test3 card", cardlist[1])

    def test_make_readme(self):
        """Ensure readme made properly"""
        with self.patch_project_dir, self.patch_readme:
            mr.MakeReadme(FAKE_PROJECT_DIR / 'tmpl.md').make_readme()
        self.assertTrue(self.README.exists())
        self.assertEqual(
            self.README.read_text(),
            Path(FAKE_PROJECT_DIR / 'correct_README.md').read_text()
        )

    def test_extra_pdf_file(self):
        """Should work, but produce a "hey, don't have a template" warning"""
        outfile = FAKE_PROJECT_DIR / 'out' / 'test4.pdf'
        shutil.copy(outfile.with_stem('test3'), outfile)
        self.files_to_delete.append(outfile)
        f = io.StringIO()
        with contextlib.redirect_stdout(f), \
                self.patch_project_dir, self.patch_readme:
            mr.MakeReadme(FAKE_PROJECT_DIR / 'tmpl.md').make_readme()
        output = f.getvalue()
        self.assertTrue(self.README.exists())
        self.assertIn('WARNING:', output)
        self.assertIn(f"{outfile.name}", output)
        self.assertIn(f"{outfile.with_suffix('.tex').name}", output)

    def tearDown(self) -> None:
        self._delete_readme()
        for f in self.files_to_delete:
            f.unlink(missing_ok=True)


class TestFailures(unittest.TestCase):
    """Test broken stuff crashes properly"""

    def test_usage(self):
        f = io.StringIO()
        with contextlib.redirect_stdout(f), self.assertRaises(SystemExit), \
                patch("sys.argv", ['make_readme.py', '-h']):
            _ = mr.parse_args()
        output = f.getvalue()
        self.assertIn('options:', output)

    def test_missing_template(self):
        f = io.StringIO()
        with contextlib.redirect_stderr(f), self.assertRaises(SystemExit), \
                patch("sys.argv", ['make_readme.py', '-t']):
            _ = mr.parse_args()
        output = f.getvalue()
        self.assertIn('expected one argument', output)

    def test_missing_option(self):
        f = io.StringIO()
        with contextlib.redirect_stderr(f), self.assertRaises(SystemExit), \
                patch("sys.argv", ['make_readme.py', '-o']):
            _ = mr.parse_args()
        output = f.getvalue()
        self.assertIn('expected one argument', output)

    def test_bad_option(self):
        f = io.StringIO()
        with contextlib.redirect_stderr(f), self.assertRaises(SystemExit), \
                patch("sys.argv", ['make_readme.py', '-o', 'q']):
            _ = mr.parse_args()
        output = f.getvalue()
        self.assertIn('invalid choice', output)

    def test_bad_option_build_file(self):
        """In case the argparse lets something bad through"""
        with self.assertRaises(ValueError):
            mr.BuildFiles('q').do_build()
