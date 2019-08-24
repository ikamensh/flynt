from contextlib import contextmanager
import io
import forbiddenfruit

read_history = {}
write_history = {}


def spy_read(func):
    def wrapper(self, *args):
        result = func(self, *args)
        read_history[self.name] = len(result)
        return result

    return wrapper


def spy_write(func):
    def wrapper(self, string, *args):
        result = func(self, string, *args)
        write_history[self.name] = len(string)
        return result

    return wrapper


def charcount_stats(filename):
    return read_history[filename], write_history[filename]


@contextmanager
def spy_on_file_io():
    orig_read = io.BufferedReader.read
    orig_write = io.TextIOWrapper.write
    forbiddenfruit.curse(io.BufferedReader, "read", spy_read(io.BufferedReader.read))
    forbiddenfruit.curse(io.TextIOWrapper, "write", spy_write(io.TextIOWrapper.write))
    yield
    forbiddenfruit.curse(io.BufferedReader, "read", orig_read)
    forbiddenfruit.curse(io.TextIOWrapper, "write", orig_write)


if __name__ == "__main__":

    with open("4.py", "w") as f:
        f.write("Hello World\n" * 10)

    print("before:", read_history, write_history)

    with spy_on_file_io():
        with open("4.py") as f:
            txt = f.read()

        with open("4.py", "w") as f:
            f.write(txt[: len(txt) // 2])

    print("after:", read_history, write_history)
