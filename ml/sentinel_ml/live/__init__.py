"""Live traffic: TShark packet fields -> bidirectional flows -> UNSW-NB15-style features.

Packet decoding is done by TShark (Wireshark's dissectors); this package only groups the
decoded fields into connections and computes the dataset's flow features from them, as
Argus did for UNSW-NB15. Several features are approximations; see ``mapping.py``.
"""
