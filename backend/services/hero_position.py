"""英雄典型位置映射（按 hero_id 升序，通过 OpenDota roles 推断）"""
# 1=Carry, 2=Mid, 3=Offlane, 4=Soft Support, 5=Hard Support
# 位置由 hero roles 自动推断，可能有偏差，请手动校准

HERO_PRIMARY: dict[int, int] = {
      1: 2,   # Anti-Mage 敌法师  [Carry, Escape, Nuker]
      2: 3,   # Axe 斧王  [Initiator, Durable, Disabler, Carry]
      3: 4,   # Bane 祸乱之源  [Support, Disabler, Nuker, Durable]
      4: 1,   # Bloodseeker 血魔  [Carry, Disabler, Nuker, Initiator]
      5: 5,   # Crystal Maiden 水晶室女  [Support, Disabler, Nuker]
      6: 1,   # Drow Ranger 卓尔游侠  [Carry, Disabler, Pusher]
      7: 4,   # Earthshaker 撼地者  [Support, Initiator, Disabler, Nuker]
      8: 1,   # Juggernaut 主宰  [Carry, Pusher, Escape]
      9: 5,   # Mirana 米拉娜  [Carry, Support, Escape, Nuker, Disabler]
     10: 1,   # Morphling 变体精灵  [Carry, Escape, Durable, Nuker, Disabler]
     11: 1,   # Shadow Fiend 影魔  [Carry, Nuker]
     12: 1,   # Phantom Lancer 幻影长矛手  [Carry, Escape, Pusher, Nuker]
     13: 2,   # Puck 帕克  [Initiator, Disabler, Escape, Nuker]
     14: [4,5],   # Pudge 帕吉  [Disabler, Initiator, Durable, Nuker]
     15: 3,   # Razor 剃刀  [Carry, Durable, Nuker, Pusher]
     16: 2,   # Sand King 沙王  [Initiator, Disabler, Support, Nuker, Escape]
     17: 2,   # Storm Spirit 风暴之灵  [Carry, Escape, Nuker, Initiator, Disabler]
     18: 1,   # Sven 斯温  [Carry, Disabler, Initiator, Durable, Nuker]
     19: 1,   # Tiny 小小  [Carry, Nuker, Pusher, Initiator, Durable, Disabler]
     20: 1,   # Vengeful Spirit 复仇之魂  [Support, Initiator, Disabler, Nuker, Escape]
     21: 1,   # Windranger 风行者  [Carry, Support, Disabler, Escape, Nuker]
     22: 2,   # Zeus 宙斯  [Nuker, Carry]
     23: 2,   # Kunkka 昆卡  [Carry, Support, Disabler, Initiator, Durable, Nuker]
     25: [2,1],   # Lina 莉娜  [Support, Carry, Nuker, Disabler]
     26: 4,   # Lion 莱恩  [Support, Disabler, Nuker, Initiator]
     27: 4,   # Shadow Shaman 暗影萨满  [Support, Pusher, Disabler, Nuker, Initiator]
     28: [3,2],   # Slardar 斯拉达  [Carry, Durable, Initiator, Disabler, Escape]
     29: 3,   # Tidehunter 潮汐猎人  [Initiator, Durable, Disabler, Nuker, Carry]
     30: [4,5],   # Witch Doctor 巫医  [Support, Nuker, Disabler]
     31: [4,5],   # Lich 巫妖  [Support, Nuker]
     32: 2,   # Riki 力丸  [Carry, Escape, Disabler]
     33: 3,   # Enigma 谜团  [Disabler, Initiator, Pusher]
     34: 2,   # Tinker 修补匠  [Carry, Nuker, Pusher]
     35: 2,   # Sniper 狙击手  [Carry, Nuker]
     36: 2,   # Necrophos 瘟疫法师  [Carry, Nuker, Durable, Disabler]
     37: 5,   # Warlock 术士  [Support, Initiator, Disabler]
     38: [3,2],   # Beastmaster 兽王  [Initiator, Disabler, Durable, Nuker]
     39: 2,   # Queen of Pain 痛苦女王  [Carry, Nuker, Escape]
     40: 4,   # Venomancer 剧毒术士  [Support, Nuker, Initiator, Pusher, Disabler]
     41: 1,   # Faceless Void 虚空假面  [Carry, Initiator, Disabler, Escape, Durable]
     42: 3,   # Wraith King 冥魂大帝  [Carry, Support, Durable, Disabler, Initiator]
     43: 2,   # Death Prophet 死亡先知  [Carry, Pusher, Nuker, Disabler]
     44: 1,   # Phantom Assassin 幻影刺客  [Carry, Escape]
     45: [4,5],   # Pugna 帕格纳  [Nuker, Pusher]
     46: [1,2],   # Templar Assassin 圣堂刺客  [Carry, Escape]
     47: 2,   # Viper 冥界亚龙  [Carry, Durable, Initiator, Disabler]
     48: 1,   # Luna 露娜  [Carry, Nuker, Pusher]
     49: [3,2],   # Dragon Knight 龙骑士  [Carry, Pusher, Durable, Disabler, Initiator, Nuker]
     50: [4,5],   # Dazzle 戴泽  [Support, Nuker, Disabler]
     51: [4,5],   # Clockwerk 发条技师  [Initiator, Disabler, Durable, Nuker]
     52: 2,   # Leshrac 拉席克  [Carry, Support, Nuker, Pusher, Disabler]
     53: [1,4],   # Nature's Prophet 先知  [Carry, Pusher, Escape, Nuker]
     54: 1,   # Lifestealer 噬魂鬼  [Carry, Durable, Escape, Disabler]
     55: 3,   # Dark Seer 黑暗贤者  [Initiator, Escape, Disabler]
     56: 1,   # Clinkz 克林克兹  [Carry, Escape, Pusher]
     57: [4,5],   # Omniknight 全能骑士  [Support, Durable, Nuker]
     58: [5,4],   # Enchantress 魅惑魔女  [Support, Pusher, Durable, Disabler]
     59: 2,   # Huskar 哈斯卡  [Carry, Durable, Initiator]
     60: 3,   # Night Stalker 暗夜魔王  [Carry, Initiator, Durable, Disabler, Nuker]
     61: 1,   # Broodmother 育母蜘蛛  [Carry, Pusher, Escape, Nuker]
     62: 4,   # Bounty Hunter 赏金猎人  [Escape, Nuker]
     63: 1,   # Weaver 编织者  [Carry, Escape]
     64: [5,4],   # Jakiro 杰奇洛  [Support, Nuker, Pusher, Disabler]
     65: [3,4],   # Batrider 蝙蝠骑士  [Initiator, Disabler, Escape]
     66: 5,   # Chen 陈  [Support, Pusher]
     67: 1,   # Spectre 幽鬼  [Carry, Durable, Escape]
     68: [4,5],   # Ancient Apparition 远古冰魄  [Support, Disabler, Nuker]
     69: 3,   # Doom 末日使者  [Carry, Disabler, Initiator, Durable, Nuker]
     70: 1,   # Ursa 熊战士  [Carry, Durable, Disabler]
     71: 4,   # Spirit Breaker 裂魂人  [Carry, Initiator, Disabler, Durable, Escape]
     72: 1,   # Gyrocopter 矮人直升机  [Carry, Nuker, Disabler]
     73: [1,4],   # Alchemist 炼金术士  [Carry, Support, Durable, Disabler, Initiator, Nuker]
     74: 2,   # Invoker 祈求者  [Carry, Nuker, Disabler, Escape, Pusher]
     75: 5,   # Silencer 沉默术士  [Carry, Support, Disabler, Initiator, Nuker]
     76: 2,   # Outworld Destroyer 殁境神蚀者  [Carry, Nuker, Disabler]
     77: 3,   # Lycan 狼人  [Carry, Pusher, Durable, Escape]
     78: 3,   # Brewmaster 酒仙  [Carry, Initiator, Durable, Disabler, Nuker]
     79: [4,5],   # Shadow Demon 暗影恶魔  [Support, Disabler, Initiator, Nuker]
     80: 1,   # Lone Druid 德鲁伊  [Carry, Pusher, Durable]
     81: 1,   # Chaos Knight 混沌骑士  [Carry, Disabler, Durable, Pusher, Initiator]
     82: 2,   # Meepo 米波  [Carry, Escape, Nuker, Disabler, Initiator, Pusher]
     83: 4,   # Treant Protector 树精卫士  [Support, Initiator, Durable, Disabler, Escape]
     84: 4,   # Ogre Magi 食人魔魔法师  [Support, Nuker, Disabler, Durable, Initiator]
     85: [4,3],   # Undying 不朽尸王  [Support, Durable, Disabler, Nuker]
     86: 4,   # Rubick 拉比克  [Support, Disabler, Nuker]
     87: 5,   # Disruptor 干扰者  [Support, Disabler, Nuker, Initiator]
     88: 4,   # Nyx Assassin 司夜刺客  [Disabler, Nuker, Initiator, Escape]
     89: 1,   # Naga Siren 娜迦海妖  [Carry, Support, Pusher, Disabler, Initiator, Escape]
     90: [4,2],   # Keeper of the Light 光之守卫  [Support, Nuker, Disabler]
     91: 5,   # Io 艾欧  [Support, Escape, Nuker]
     92: 4,   # Visage 维萨吉  [Support, Nuker, Durable, Disabler, Pusher]
     93: 1,   # Slark 斯拉克  [Carry, Escape, Disabler, Nuker]
     94: 1,   # Medusa 美杜莎  [Carry, Disabler, Durable]
     95: 1,   # Troll Warlord 巨魔战将  [Carry, Pusher, Disabler, Durable]
     96: 3,   # Centaur Warrunner 半人马战行者  [Durable, Initiator, Disabler, Nuker, Escape]
     97: 3,   # Magnus 马格纳斯  [Initiator, Disabler, Nuker, Escape]
     98: 3,   # Timbersaw 伐木机  [Nuker, Durable, Escape]
     99: 3,   # Bristleback 钢背兽  [Carry, Durable, Initiator, Nuker]
    100: 4,   # Tusk 巨牙海民  [Initiator, Disabler, Nuker]
    101: [4,2],   # Skywrath Mage 天怒法师  [Support, Nuker, Disabler]
    102: 1,   # Abaddon 亚巴顿  [Support, Carry, Durable]
    103: 5,   # Elder Titan 上古巨神  [Initiator, Disabler, Nuker, Durable]
    104: 3,   # Legion Commander 军团指挥官  [Carry, Disabler, Initiator, Durable, Nuker]
    105: 4,   # Techies 工程师  [Nuker, Disabler]
    106: 2,   # Ember Spirit 灰烬之灵  [Carry, Escape, Nuker, Disabler, Initiator]
    107: 2,   # Earth Spirit 大地之灵  [Nuker, Escape, Disabler, Initiator, Durable]
    108: 3,   # Underlord 孽主  [Support, Nuker, Disabler, Durable, Escape]
    109: 1,   # Terrorblade 恐怖利刃  [Carry, Pusher, Nuker]
    110: [4,5],   # Phoenix 凤凰  [Support, Nuker, Initiator, Escape, Disabler]
    111: [5,4],   # Oracle 神谕者  [Support, Nuker, Disabler, Escape]
    112: [5,4],   # Winter Wyvern 寒冬飞龙  [Support, Disabler, Nuker]
    113: 2,   # Arc Warden 天穹守望者  [Carry, Escape, Nuker]
    114: 1,   # Monkey King 齐天大圣  [Carry, Escape, Disabler, Initiator]
    119: 4,   # Dark Willow 邪影芳灵  [Support, Nuker, Disabler, Escape]
    120: 2,   # Pangolier 石鳞剑士  [Carry, Nuker, Disabler, Durable, Escape, Initiator]
    121: 4,   # Grimstroke 天涯墨客  [Support, Nuker, Disabler, Escape]
    123: 4,   # Hoodwink 森海飞霞  [Support, Nuker, Escape, Disabler]
    126: 2,   # Void Spirit 虚无之灵  [Carry, Escape, Nuker, Disabler]
    128: 2,   # Snapfire 电炎绝手  [Support, Nuker, Disabler, Escape]
    129: 3,   # Mars 玛尔斯  [Carry, Initiator, Disabler, Durable]
    131: 4,   # Ringmaster 百戏大王  [Support, Nuker, Escape, Disabler]
    135: 3,   # Dawnbreaker 破晓辰星  [Carry, Durable]
    136: [3,2,4],   # Marci 玛西  [Support, Carry, Initiator, Disabler, Escape]
    137: 3,   # Primal Beast 兽  [Initiator, Durable, Disabler]
    138: 1,   # Muerta 琼英碧灵  [Carry, Nuker, Disabler]
    145: 1,   # Kez 凯  [Carry, Escape, Disabler]
    155: 3,   # Largo Largo  [Durable, Disabler, Support]
}

HERO_SECONDARY: dict[int, list[int]] = {
      1: [1],   # Anti-Mage 敌法师
      3: [3],   # Bane 祸乱之源
      4: [3,2],   # Bloodseeker 血魔
      5: [4],   # Crystal Maiden 水晶室女
      7: [2,3],   # Earthshaker 撼地者
      8: [4],   # Juggernaut 主宰
      9: [4],   # Mirana 米拉娜
     11: [2],   # Shadow Fiend 影魔
     13: [3],   # Puck 帕克
     14: [1,3],   # Pudge 帕吉
     15: [1],   # Razor 剃刀
     16: [3],   # Sand King 沙王
     17: [1],   # Storm Spirit 风暴之灵
     18: [1],   # Sven 斯温
     19: [4],   # Tiny 小小
     20: [4,5],   # Vengeful Spirit 复仇之魂
     21: [4,3,5],   # Windranger 风行者
     22: [4,5],   # Zeus 宙斯
     23: [4],   # Kunkka 昆卡
     25: [4],   # Lina 莉娜
     26: [5,2],   # Lion 莱恩
     27: [5],   # Shadow Shaman 暗影萨满
     28: [1],   # Slardar 斯拉达
     29: [1],   # Tidehunter 潮汐猎人
     30: [5],   # Witch Doctor 巫医
     31: [5],   # Lich 巫妖
     32: [1],   # Riki 力丸
     34: [4],   # Tinker 修补匠
     35: [4],   # Sniper 狙击手
     36: [1,3],   # Necrophos 瘟疫法师
     37: [4],   # Warlock 术士
     38: [1],   # Beastmaster 兽王
     39: [4,3,1],   # Queen of Pain 痛苦女王
     40: [3,5],   # Venomancer 剧毒术士
     42: [1,4],   # Wraith King 冥魂大帝
     46: [2],   # Templar Assassin 圣堂刺客
     49: [1],   # Dragon Knight 龙骑士
     50: [5],   # Dazzle 戴泽
     52: [4],   # Leshrac 拉席克
     53: [2],   # Nature's Prophet 先知
     56: [4],   # Clinkz 克林克兹
     57: [3],   # Omniknight 全能骑士
     58: [3],   # Enchantress 魅惑魔女
     60: [1],   # Night Stalker 暗夜魔王
     61: [2,3],   # Broodmother 育母蜘蛛
     62: [5],   # Bounty Hunter 赏金猎人  [Escape, Nuker]
     63: [4],   # Weaver 编织者
     64: [5],   # Jakiro 杰奇洛
     65: [5],   # Batrider 蝙蝠骑士
     66: [4],   # Chen 陈
     68: [5],   # Ancient Apparition 远古冰魄
     69: [1],   # Doom 末日使者
     71: [3],   # Spirit Breaker 裂魂人
     72: [4],   # Gyrocopter 矮人直升机
     73: [1, 4],   # Alchemist 炼金术士
     74: [4],   # Invoker 祈求者
     75: [4],   # Silencer 沉默术士
     81: [3],   # Chaos Knight 混沌骑士 
     82: [1, 3],   # Meepo 米波
     83: [5],   # Treant Protector 树精卫士
     84: [2,5,3],   # Ogre Magi 食人魔魔法师
     85: [5],   # Undying 不朽尸王
     86: [5],   # Rubick 拉比克
     87: [4],   # Disruptor 干扰者
     88: [5,3],   # Nyx Assassin 司夜刺客
     89: [4],   # Naga Siren 娜迦海妖
     90: [5],   # Keeper of the Light 光之守卫
     91: [1,4],   # Io 艾欧
     92: [3],   # Visage 维萨吉
     93: [2,3],   # Slark 斯拉克
     97: [1],   # Magnus 马格纳斯
     99: [1],   # Bristleback 钢背兽
    100: [5],   # Tusk 巨牙海民
    101: [5],   # Skywrath Mage 天怒法师
    102: [3,4,5],   # Abaddon 亚巴顿
    103: [4],   # Elder Titan 上古巨神
    107: [5,4],   # Earth Spirit 大地之灵
    110: [3],   # Phoenix 凤凰
    113: [1],   # Arc Warden 天穹守望者
    114: [3,2],   # Monkey King 齐天大圣
    119: [5],   # Dark Willow 邪影芳灵
    120: [3],   # Pangolier 石鳞剑士
    121: [5],   # Grimstroke 天涯墨客
    123: [5],   # Hoodwink 森海飞霞
    128: [4,5],   # Snapfire 电炎绝手
    131: [5],   # Ringmaster 百戏大王
    135: [5],   # Dawnbreaker 破晓辰星 
    136: [1],   # Marci 玛西
    138: [4,2],   # Muerta 琼英碧灵
}


def guess_position(hero_id: int, gpm: int, team_players: list[dict]) -> int:
    """已废弃——实际逻辑见 position_detector.py"""
    primary = HERO_PRIMARY.get(hero_id)
    if primary is None:
        sorted_by_gpm = sorted(team_players, key=lambda x: x.get("gold_per_min", 0), reverse=True)
        for i, tp in enumerate(sorted_by_gpm):
            if tp.get("hero_id") == hero_id:
                return i + 1
        return 3
    return primary
