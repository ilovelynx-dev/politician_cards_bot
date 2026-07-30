import random


class Politician:
    def __init__(self, id: str, name: str, aliases: list[str], influence: int,
                 charisma: int, stamina: int, weight: int = 50, description: str = ""):
        self.id = id
        self.name = name
        self.aliases = [a.lower() for a in aliases]
        self.influence = influence
        self.charisma = charisma
        self.stamina = stamina
        self.weight = weight
        self.description = description

    @property
    def power(self) -> int:
        return (self.influence + self.charisma + self.stamina) // 3

    def matches_name(self, text: str) -> bool:
        t = text.strip().lower()
        return any(a in t or t in a for a in self.aliases + [self.name.lower()])


class PoliticianManager:
    def __init__(self):
        self.all: list[Politician] = []
        self.boss: Politician | None = None
        self._by_id: dict[str, Politician] = {}
        self._init_politicians()

    def _init_politicians(self):
        data = [
            Politician("putin", "Владимир Путин", ["путин", "putin", "ввп", "vov"], 95, 85, 90, weight=80,
                       description="Президент Российской Федерации"),
            Politician("lukashenko", "Александр Лукашенко", ["лукашенко", "lukashenko", "батька", "batka"], 75, 70, 80, weight=60,
                       description="Президент Республики Беларусь"),
            Politician("trump", "Дональд Трамп", ["трамп", "trump", "дональд", "donald"], 85, 90, 80, weight=75,
                       description="45-й президент США"),
            Politician("macron", "Эммануэль Макрон", ["макрон", "macron", "эммануэль", "emmanuel"], 70, 75, 70, weight=55,
                       description="Президент Франции"),
            Politician("scholz", "Олаф Шольц", ["шольц", "scholz", "олаф", "olaf"], 65, 55, 60, weight=50,
                       description="Канцлер Германии"),
            Politician("xi", "Си Цзиньпин", ["си", "xi", "цзиньпин", "jinping", "си цзиньпин"], 95, 80, 85, weight=85,
                       description="Председатель КНР"),
            Politician("kim", "Ким Чен Ын", ["ким", "kim", "чен", "chen", "un", "кчы"], 85, 60, 90, weight=70,
                       description="Председатель КНДР"),
            Politician("merkel", "Ангела Меркель", ["меркель", "merkel", "ангела", "angela"], 80, 75, 85, weight=70,
                       description="Бывший канцлер Германии"),
            Politician("zelensky", "Владимир Зеленский", ["зеленский", "zelensky", "зеля", "zelya"], 75, 85, 75, weight=65,
                       description="Президент Украины"),
            Politician("navalny", "Алексей Навальный", ["навальный", "navalny", "алексей", "alexey"], 65, 80, 70, weight=60,
                       description="Оппозиционный политик"),
            Politician("medvedev", "Дмитрий Медведев", ["медведев", "medvedev", "дмитрий", "dmitry"], 60, 50, 55, weight=45,
                       description="Зампред Совета Безопасности РФ"),
            Politician("shoigu", "Сергей Шойгу", ["шойгу", "shoigu", "сергей", "sergey"], 75, 65, 85, weight=65,
                       description="Министр обороны РФ"),
            Politician("lavrov", "Сергей Лавров", ["лавров", "lavrov", "сергей", "sergey"], 80, 75, 80, weight=65,
                       description="Министр иностранных дел РФ"),
            Politician("modi", "Нарендра Моди", ["моди", "modi", "нарендра", "narendra"], 80, 85, 85, weight=70,
                       description="Премьер-министр Индии"),
            Politician("sunak", "Риши Сунак", ["сунак", "sunak", "риши", "rishi"], 60, 55, 55, weight=45,
                       description="Премьер-министр Великобритании"),
            Politician("putin_old", "Владимир Путин (молодой)", ["путин молодой", "молодой путин", "putin young"], 70, 90, 95, weight=55,
                       description="Молодой Владимир Путин"),
        ]
        self.all = data
        self._by_id = {p.id: p for p in data}
        self.boss = Politician("biden", "Джо Байден", ["байден", "biden", "джо", "joe", "sleepy joe"], 99, 99, 99,
                               description="Бывший президент США")

    def get(self, politician_id: str) -> Politician | None:
        return self._by_id.get(politician_id)

    def get_random(self) -> Politician:
        weights = [p.weight for p in self.all]
        return random.choices(self.all, weights=weights, k=1)[0]

    def search(self, query: str) -> list[Politician]:
        q = query.lower()
        return [p for p in self.all if q in p.name.lower() or any(q in a for a in p.aliases)]


politicians = PoliticianManager()
