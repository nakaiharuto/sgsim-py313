# realtime_node.py
class MVCompat:
    """sg_draw が呼ぶ common_prefix_length() だけ合わせる薄いラッパ"""
    def __init__(self, bitstr: str):
        self.bitstr = bitstr

    def common_prefix_length(self, other):
        # other は sg.MembershipVector のはず。str()で文字列化して比較する
        o = str(other)
        cnt = 0
        for a, b in zip(self.bitstr, o):
            if a == b:
                cnt += 1
            else:
                break
        return cnt

    def __str__(self):
        return self.bitstr


class RealNode:
    """sg_draw.ingredients() が要求する最低限の属性/メソッドだけ持つ"""
    def __init__(self, key: int, mv: str, neighbors: list[dict]):
        self.key = key
        self.mv = MVCompat(mv)          # .common_prefix_length() を持たせる
        self._neighbors = {nb["level"]: nb for nb in neighbors}

    def left(self, level: int):
        nb = self._neighbors.get(level)
        if not nb or not nb["LEFT"]:
            return None
        return nb["LEFT"][0]

    def right(self, level: int):
        nb = self._neighbors.get(level)
        if not nb or not nb["RIGHT"]:
            return None
        return nb["RIGHT"][0]
