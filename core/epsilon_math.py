class Epsilon:
    def __init__(self, real: float, eps: float = 0.0):
        self.real = float(real)
        self.eps = float(eps)

    def __add__(self, other):
        if isinstance(other, Epsilon):
            return Epsilon(self.real + other.real, self.eps + other.eps)
        return Epsilon(self.real + other, self.eps)

    def __radd__(self, other):
        return self.__add__(other)

    def __sub__(self, other):
        if isinstance(other, Epsilon):
            return Epsilon(self.real - other.real, self.eps - other.eps)
        return Epsilon(self.real - other, self.eps)

    def __rsub__(self, other):
        if isinstance(other, (int, float)):
            return Epsilon(other - self.real, -self.eps)
        return NotImplemented

    def __mul__(self, scalar):
        if isinstance(scalar, (int, float)):
            return Epsilon(self.real * scalar, self.eps * scalar)
        return NotImplemented

    def __rmul__(self, scalar):
        return self.__mul__(scalar)

    def __eq__(self, other):
        if isinstance(other, Epsilon):
            return abs(self.real - other.real) < 1e-9 and abs(self.eps - other.eps) < 1e-9
        if isinstance(other, (int, float)):
            return abs(self.real - other) < 1e-9 and abs(self.eps) < 1e-9
        return False

    def __lt__(self, other):
        other_real = other.real if isinstance(other, Epsilon) else float(other)
        other_eps = other.eps if isinstance(other, Epsilon) else 0.0

        if abs(self.real - other_real) > 1e-9:
            return self.real < other_real
        return self.eps < other_eps

    def __le__(self, other):
        return self < other or self == other

    def __gt__(self, other):
        return not (self <= other)

    def __ge__(self, other):
        return not (self < other)

    def __str__(self):
        r_str = f"{self.real:g}"
        if abs(self.eps) < 1e-9:
            return r_str

        eps_str = f"{abs(self.eps):g}ε" if abs(abs(self.eps) - 1.0) > 1e-9 else "ε"

        if abs(self.real) < 1e-9:
            return eps_str if self.eps > 0 else f"-{eps_str}"

        sign = "+" if self.eps > 0 else "-"
        return f"{r_str} {sign} {eps_str}"

    def __repr__(self):
        return self.__str__()
