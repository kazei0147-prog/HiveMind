"""
DataSource 抽象层 - HiveMind v0.6

替换合成观测为真实数据源，支持 CSV、API、多源混合。
设计原则：插拔式——不改动 mother.py 核心循环，只替换 _generate_observation()。
"""

from abc import ABC, abstractmethod
import csv
import random
import logging
from pathlib import Path
from typing import Optional, List

logger = logging.getLogger("hivemind.datasource")


class DataSource(ABC):
    """数据源抽象基类"""

    @abstractmethod
    def fetch(self) -> Optional[float]:
        """获取下一个数据点。返回 None 表示数据耗尽。"""
        ...

    @abstractmethod
    def reset(self):
        """重置数据源到起始位置"""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    @abstractmethod
    def size(self) -> int:
        """数据总量（-1 表示无限或未知）"""
        ...


class SyntheticSource(DataSource):
    """
    合成数据源（向后兼容 v0.1-v0.5）。

    基于 target_value + 高斯噪声生成数据，用于对照实验。
    """

    def __init__(self, target: float = 50.0, noise: float = 10.0):
        self.target = target
        self.noise = noise
        self._count = 0

    def fetch(self) -> float:
        self._count += 1
        return self.target + random.gauss(0, self.noise)

    def reset(self):
        self._count = 0

    @property
    def name(self) -> str:
        return f"Synthetic(target={self.target}, noise={self.noise})"

    @property
    def size(self) -> int:
        return -1  # 无限


class CSVSource(DataSource):
    """
    CSV 文件数据源。

    读取单列数值 CSV，按顺序逐行返回。
    到达末尾后可选择循环或返回 None。
    """

    def __init__(self, filepath: str, column: str = "value", loop: bool = True):
        self.filepath = Path(filepath)
        self.column = column
        self.loop = loop
        self._data: List[float] = []
        self._cursor = 0
        self._load()

    def _load(self):
        """加载 CSV 到内存"""
        with open(self.filepath, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            self._data = [float(row[self.column]) for row in reader if row.get(self.column)]
        logger.info(f"CSVSource 加载 {len(self._data)} 个数据点: {self.filepath}")

    def fetch(self) -> Optional[float]:
        if not self._data:
            return None
        if self._cursor >= len(self._data):
            if self.loop:
                self._cursor = 0
            else:
                return None
        value = self._data[self._cursor]
        self._cursor += 1
        return value

    def reset(self):
        self._cursor = 0

    @property
    def name(self) -> str:
        return f"CSV({self.filepath.name})"

    @property
    def size(self) -> int:
        return len(self._data)


class MultiSource(DataSource):
    """
    多源混合数据源。

    按权重从多个子源中交替采样，模拟"信息来自不同渠道"。
    """

    def __init__(self, sources: List[DataSource], weights: Optional[List[float]] = None):
        self.sources = sources
        self.weights = weights or [1.0 / len(sources)] * len(sources)

    def fetch(self) -> Optional[float]:
        """按权重随机选择一个子源采样"""
        source = random.choices(self.sources, weights=self.weights, k=1)[0]
        return source.fetch()

    def reset(self):
        for s in self.sources:
            s.reset()

    @property
    def name(self) -> str:
        return f"Multi({', '.join(s.name for s in self.sources)})"

    @property
    def size(self) -> int:
        return sum(s.size for s in self.sources if s.size > 0)


class NoisySource(DataSource):
    """
    噪声包装器：给任何数据源添加高斯噪声。

    模拟"真实世界的不完美测量"。
    """

    def __init__(self, source: DataSource, noise_std: float = 2.0):
        self.source = source
        self.noise_std = noise_std

    def fetch(self) -> Optional[float]:
        val = self.source.fetch()
        if val is None:
            return None
        return val + random.gauss(0, self.noise_std)

    def reset(self):
        self.source.reset()

    @property
    def name(self) -> str:
        return f"Noisy({self.source.name}, σ={self.noise_std})"

    @property
    def size(self) -> int:
        return self.source.size
