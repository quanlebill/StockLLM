
class Base:
    __slots__ = ()
    def to_dict(self) -> dict:
        for cls in self.__class__.__mro__:
            if hasattr(cls, "__slots__"):
                return {attr: getattr(self, attr) for attr in cls.__slots__}

        return {}

class EffectSizeTTest(Base):
    __slots__ = ("pearson_correlation", "pearson_label", "cohen_d", "cohen_d_label",)
    def __init__(self):
        super().__init__()
        self.pearson_correlation = None
        self.pearson_label = None
        self.cohen_d = None
        self.cohen_d_label = None

class EffectSizeChiTest(Base):
    __slots__ = ("cramer_v", "cramer_v_label")
    def __init__(self):
        super().__init__()
        self.cramer_v = None
        self.cramer_v_label = None


class StabilityTest(Base):
    __slots__= ("splitting_window_score", "rolling_window_score", "sampling_score", "final_score", "number_of_iterations")
    def __init__(self):
        super().__init__()
        self.splitting_window_score = None
        self.rolling_window_score = None
        self.sampling_score = None
        self.final_score = None
        self.number_of_iterations = None

class DescriptiveStat(Base):
    __slots__ = ("mean", "std","variance")
    def __init__(self):
        super().__init__()
        self.mean = None
        self.std = None
        self.variance = None

if __name__ == "__main__":
    effect_size_test = EffectSizeTTest()
    print(effect_size_test.to_dict())