def find_cycle(celula_start: tuple[int, int], celule_baza: set[tuple[int, int]]) -> list[tuple[int, int]]:
    celule_valide = set(celule_baza)
    celule_valide.add(celula_start)

    def dfs(curent: tuple[int, int], directie: str, vizitate: set, drum: list) -> list | None:
        if len(drum) >= 4 and curent == celula_start:
            return drum

        r, c = curent

        if directie == 'H' or directie is None:

            for nr, nc in celule_valide:
                if nc == c and nr != r:
                    if (nr, nc) == celula_start and len(drum) >= 3:
                        return drum + [(nr, nc)]
                    if (nr, nc) not in vizitate:
                        vizitate.add((nr, nc))
                        res = dfs((nr, nc), 'V', vizitate, drum + [(nr, nc)])
                        if res:
                            return res
                        vizitate.remove((nr, nc))

        if directie == 'V' or directie is None:

            for nr, nc in celule_valide:
                if nr == r and nc != c:
                    if (nr, nc) == celula_start and len(drum) >= 3:
                        return drum + [(nr, nc)]
                    if (nr, nc) not in vizitate:
                        vizitate.add((nr, nc))
                        res = dfs((nr, nc), 'H', vizitate, drum + [(nr, nc)])
                        if res:
                            return res
                        vizitate.remove((nr, nc))

        return None

    set_vizitate = {celula_start}
    circuit = dfs(celula_start, None, set_vizitate, [celula_start])

    if circuit:

        return circuit[:-1]

    return []
