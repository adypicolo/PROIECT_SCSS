import copy
from core.epsilon_math import Epsilon
from utils.cycle_finder import find_cycle

class TransportationSolver:
    def __init__(self, matrice_costuri: list[list[float]], disponibil: list[float], necesar: list[float]):
        self.cost = copy.deepcopy(matrice_costuri)
        self.disponibil = copy.deepcopy(disponibil)
        self.necesar = copy.deepcopy(necesar)
        self.m = len(self.disponibil)
        self.n = len(self.necesar)

        self.original_m = self.m
        self.original_n = self.n

        self.echilibreaza_problema()

    def echilibreaza_problema(self):
        suma_disponibil = sum(self.disponibil)
        suma_necesar = sum(self.necesar)

        if suma_disponibil > suma_necesar:
            self.necesar.append(suma_disponibil - suma_necesar)
            for row in self.cost:
                row.append(0.0)
            self.n += 1
        elif suma_necesar > suma_disponibil:
            self.disponibil.append(suma_necesar - suma_disponibil)
            self.cost.append([0.0] * self.n)
            self.m += 1

    def solutia_initiala_nv(self, foloseste_perturbare=False) -> dict[tuple[int, int], Epsilon]:
        supp = [Epsilon(x) for x in self.disponibil]
        dem = [Epsilon(x) for x in self.necesar]

        if foloseste_perturbare:
            supp[0] = supp[0] + Epsilon(0, 1)
            dem[-1] = dem[-1] + Epsilon(0, 1)

        alocari = {}
        i, j = 0, 0

        while i < self.m and j < self.n:
            val = supp[i] if supp[i] < dem[j] else dem[j]
            alocari[(i, j)] = val

            supp[i] = supp[i] - val
            dem[j] = dem[j] - val

            if supp[i] == 0 and dem[j] == 0:
                i += 1
                j += 1
            elif supp[i] == 0:
                i += 1
            else:
                j += 1
        return alocari

    def cell_name(self, r, c):
        return f"(A{r + 1}, B{c + 1})"

    def solve(self):
        supp_afisare = [Epsilon(x) for x in self.disponibil]
        dem_afisare = [Epsilon(x) for x in self.necesar]

        alocari = self.solutia_initiala_nv(foloseste_perturbare=False)

        foloseste_perturbare = False
        if len(alocari) < self.m + self.n - 1:
            alocari = self.solutia_initiala_nv(foloseste_perturbare=True)
            supp_afisare[0] = supp_afisare[0] + Epsilon(0, 1)
            dem_afisare[-1] = dem_afisare[-1] + Epsilon(0, 1)
            foloseste_perturbare = True

        iteratie = 0
        while True:
            celule_baza = set(alocari.keys())

            u = {0: 0.0}
            v = {}
            schimbat = True
            while schimbat and (len(u) < self.m or len(v) < self.n):
                schimbat = False
                for (i, j) in celule_baza:
                    if i in u and j not in v:
                        v[j] = self.cost[i][j] - u[i]
                        schimbat = True
                    elif j in v and i not in u:
                        u[i] = self.cost[i][j] - v[j]
                        schimbat = True

            u_list = [u.get(i, None) for i in range(self.m)]
            v_list = [v.get(j, None) for j in range(self.n)]

            delta = {}
            for i in range(self.m):
                for j in range(self.n):
                    if (i, j) not in celule_baza:
                        if u_list[i] is not None and v_list[j] is not None:
                            delta[(i, j)] = self.cost[i][j] - (u_list[i] + v_list[j])

            delta_minim = 0
            pivot = None
            for cell, d in delta.items():
                if d < delta_minim:
                    delta_minim = d
                    pivot = cell

            este_optim = pivot is None

            cost_curent = Epsilon(0)
            for (r, c), cant in alocari.items():
                cost_curent = cost_curent + (cant * self.cost[r][c])

            if este_optim:
                for k in alocari:
                    alocari[k] = Epsilon(alocari[k].real, 0)

                mesaj = f"Toate costurile marginale (delta) sunt >= 0.\nSOLUTIA ESTE OPTIMA!\nCost total minim final: {cost_curent}"

                yield {
                    'iteratie': iteratie,
                    'alocari': copy.deepcopy(alocari),
                    'u': u_list, 'v': v_list, 'delta': delta,
                    'pivot': None, 'circuit': None, 'este_optim': True,
                    'cost': self.cost, 'm': self.m, 'n': self.n,
                    'original_m': self.original_m,
                    'original_n': self.original_n,
                    'disp': supp_afisare, 'nec': dem_afisare,
                    'mesaj_explicativ': mesaj
                }
                break

            circuit = find_cycle(pivot, celule_baza)
            celule_minus = circuit[1::2]

            valoare_theta = alocari[celule_minus[0]]
            celula_iesire = celule_minus[0]

            for cell in celule_minus[1:]:
                if alocari[cell] < valoare_theta:
                    valoare_theta = alocari[cell]
                    celula_iesire = cell

            mesaj = f"Cost total la acest pas: {cost_curent}\n\n"
            if iteratie == 0:
                mesaj += "Solutia initiala a fost calculata prin Metoda Coltului Nord-Vest.\n"
                if foloseste_perturbare:
                    mesaj += "S-a detectat o problema degenerata. S-a aplicat perturbarea cu epsilon (e).\n"

            circuit_str = " -> ".join([self.cell_name(r, c) for r, c in circuit])
            mesaj += (
                f"Solutia nu este optima. Cel mai negativ cost marginal este {delta_minim:g} la celula {self.cell_name(*pivot)}.\n"
                f"Se formeaza circuitul de compensare: {circuit_str}\n"
                f"Se transfera cantitatea theta = {valoare_theta} pe circuit.\n"
                f"Celula care va iesi din baza este {self.cell_name(*celula_iesire)}.")

            yield {
                'iteratie': iteratie,
                'alocari': copy.deepcopy(alocari),
                'u': u_list, 'v': v_list, 'delta': delta,
                'pivot': pivot, 'circuit': circuit, 'este_optim': False,
                'cost': self.cost, 'm': self.m, 'n': self.n,
                'original_m': self.original_m,
                'original_n': self.original_n,
                'disp': supp_afisare, 'nec': dem_afisare,
                'mesaj_explicativ': mesaj
            }

            for idx, cell in enumerate(circuit):
                if cell == pivot:
                    alocari[cell] = valoare_theta
                elif idx % 2 == 0:
                    alocari[cell] = alocari[cell] + valoare_theta
                else:
                    alocari[cell] = alocari[cell] - valoare_theta

            del alocari[celula_iesire]
            iteratie += 1
