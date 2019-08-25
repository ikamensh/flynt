from contextlib import contextmanager
import io
import forbiddenfruit

READ_HISTORY = {}
WRITE_HISTORY = {}


def spy_read(func):
    def wrapper(self, *args):
        result = func(self, *args)
        READ_HISTORY[self.name] = len(result)
        return result

    return wrapper


def spy_write(func):
    def wrapper(self, string, *args):
        result = func(self, string, *args)
        WRITE_HISTORY[self.name] = len(string)
        return result

    return wrapper


def charcount_stats(filename):
    return READ_HISTORY[filename], WRITE_HISTORY[filename]


@contextmanager
def spy_on_file_io():
    orig_read = io.BufferedReader.read
    orig_write = io.TextIOWrapper.write
    forbiddenfruit.curse(io.BufferedReader, "read", spy_read(io.BufferedReader.read))
    forbiddenfruit.curse(io.TextIOWrapper, "write", spy_write(io.TextIOWrapper.write))
    yield
    forbiddenfruit.curse(io.BufferedReader, "read", orig_read)
    forbiddenfruit.curse(io.TextIOWrapper, "write", orig_write)


def main():
    with open("4.py", "w") as file:
        file.write("Hello World\n" * 10)

    print("before:", READ_HISTORY, WRITE_HISTORY)

    with spy_on_file_io():
        with open("4.py") as file:
            txt = file.read()

        with open("4.py", "w") as file:
            file.write(txt[: len(txt) // 2])

    print("after:", READ_HISTORY, WRITE_HISTORY)


if __name__ == "__main__":
    main()
