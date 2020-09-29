import re
from functools import total_ordering
from mavehgvs.patterns.shared import pos

pos_extended: str = rf"(?P<position>{pos})|(?P<position_intron>{pos}[+-]{pos})|(?P<position_utr>[*-]{pos})|(?P<position_utr_intron>[*-]{pos}[+-]{pos})"
"""str: Pattern matching a position relative to a transcript with match groups.

This pattern is used for sequence positions in a spliced transcript or coding sequence that are found in a UTR or
intron. It does not match integer-only positions.
"""


@total_ordering
class VariantPosition:
    _fullmatch = re.compile(pos_extended, flags=re.ASCII).fullmatch
    """Callable[[str, int, int], Optional[Match[str]]]: fullmatch callable for parsing positions
    
    Returns a match object if the full string matches one of the position groups in :py:data:`pos_extended`.
    """

    def __init__(self, pos_str: str) -> None:
        """Class for storing a variant position.

        The class includes special fields for variants using the extended position syntax.

        Parameters
        ----------
        pos_str : str
            The string to convert to a VariantPosition object.

        Attributes
        ----------
        position : Optional[int]
            The integer position. None for UTR positions.
        intronic_position : Optional[int]
            The number of bases into the intron for intronic positions.
            Nucleotides towards the 5' end of the intron have positive intronic_position and their position is that of
            the last base of the 5' exon.
            Nucleotides towards the 3' end of the intron have negative intronic_position and their position is that of
            the first base of the 3' exon.
            None for non-intronic positions.
        utr : Optional[str]
            Either "5p" or "3p" for 5' or 3' UTR positions. None for all other positions.
        utr_position : Optional[int]
            The number of bases into the 5' or 3' UTR for UTR positions. None for all other positions.

        """
        try:
            gdict = VariantPosition._fullmatch(pos_str).groupdict()
        except AttributeError:
            raise ValueError(f"invalid variant position string '{pos_str}'")

        self.position = None
        self.intronic_position = None
        self.utr = None
        self.utr_position = None

        if gdict["position"] is not None:
            self.position = int(gdict["position"])

        elif gdict["position_intron"] is not None:
            if "+" in gdict["position_intron"]:
                self.position, self.intronic_position = (
                    int(x) for x in gdict["position_intron"].split("+")
                )
            elif "-" in gdict["position_intron"]:
                self.position, self.intronic_position = (
                    int(x) for x in gdict["position_intron"].split("-")
                )
                self.intronic_position *= -1
            else:  # pragma: no cover
                raise ValueError("unexpected intronic position separator")

        elif gdict["position_utr"] is not None:
            if gdict["position_utr"].startswith("*"):
                self.utr = "3p"
            elif gdict["position_utr"].startswith("-"):
                self.utr = "5p"
            else:  # pragma: no cover
                raise ValueError("unexpected UTR symbol")
            self.utr_position = int(gdict["position_utr"][1:])

        elif gdict["position_utr_intron"] is not None:
            if gdict["position_utr_intron"].startswith("*"):
                self.utr = "3p"
            elif gdict["position_utr_intron"].startswith("-"):
                self.utr = "5p"
            else:  # pragma: no cover
                raise ValueError("unexpected UTR symbol")
            if "+" in gdict["position_utr_intron"][1:]:
                self.utr_position, self.intronic_position = (
                    int(x) for x in gdict["position_utr_intron"][1:].split("+")
                )
            elif "-" in gdict["position_intron"][1:]:
                self.utr_position, self.intronic_position = (
                    int(x) for x in gdict["position_utr_intron"][1:].split("-")
                )
                self.intronic_position *= -1
            else:  # pragma: no cover
                raise ValueError("unexpected intronic position separator")

        else:  # pragma: no cover
            raise ValueError("unexpected position format")

    def is_utr(self) -> bool:
        """Return whether this is a UTR position.

        Returns
        -------
        bool
            True if the object describes a position in the UTR; else False.

        """
        if self.utr is not None:
            return True
        else:
            return False

    def is_intronic(self) -> bool:
        """Return whether this is an intronic position.

        Returns
        -------
        bool
            True if the object describes a position in an intron; else False.

        """
        if self.intronic_position is not None:
            return True
        else:
            return False

    def is_extended(self) -> bool:
        """Return whether this position was described using the extended syntax.

        Returns
        -------
        bool
            True if the position was described using the extended syntax; else False.

        """
        return self.is_intronic() or self.is_utr()

    # the string annotation used in the type hint below is required for Python 3.6 compatibility
    def is_adjacent(self, other: "VariantPosition") -> bool:
        """Return whether this variant and another are immediately adjacent in sequence space.

        .. note:: The special case involving the last variant in a transcript sequence and the first base in the 3'
           UTR will be evaluated as not adjacent, as the object does not have sequence length information.

        Parameters
        ----------
        other : VariantPosition
            The object to calculate adjacency to.

        Returns
        -------
        bool
            True if the positions describe adjacent bases in sequence space; else False.

        """
        # both variants describe simple positions
        if not self.is_extended() and not other.is_extended():
            if abs(self.position - other.position) == 1:
                return True
            else:
                return False
        else:
            # TODO: implement the rest of the adjacency checks
            pass

    def __lt__(self, other: "VariantPosition") -> bool:
        """Less than comparison operator.

        Other comparison operators will be filled in using :py:func:`functools.total_ordering`.

        Parameters
        ----------
        other : VariantPosition
            The other VariantPosition to compare to.

        Returns
        -------
        bool
            True if this position evaluates as strictly less than the other position; else False.

        """

        def intron_lt(a: "VariantPosition", b: "VariantPosition") -> bool:
            """Compare two positions based on their intronic positions assuming the positions are otherwise equal.

            Parameters
            ----------
            a : VariantPosition
                The first position to compare.
            b : VariantPosition
                The second position to compare.

            Returns
            -------
            bool
                True if a is strictly less than b based on the intronic position, assuming that all other fields are
                equal.

            """
            if a.intronic_position == b.intronic_position:  # variants must be equal
                return False
            elif a.intronic_position is None:
                return b.intronic_position < 0
            elif b.intronic_position is None:
                return a.intronic_position < 0
            else:
                return a.intronic_position < b.intronic_position

        if self.utr == other.utr:
            if self.utr is not None:
                if self.utr_position != other.utr_position:
                    return self.utr_position < other.utr_position
                else:
                    return intron_lt(self, other)
            else:  # both are not UTR positions
                if self.position != other.position:
                    return self.position < other.position
                else:
                    return intron_lt(self, other)
        else:  # 5p < non-UTR < 3p
            if self.utr == "5p" or other.utr == "3p":
                return True
            elif self.utr == "3p" or other.utr == "5p":
                return False

    def __eq__(self, other: "VariantPosition") -> bool:
        """Equality comparison operator.

        Other comparison operators will be filled in using :py:func:`functools.total_ordering`.

        Parameters
        ----------
        other : VariantPosition
            The other VariantPosition to compare to.

        Returns
        -------
        bool
            True if this position is the same as the other position; else False.

        """
        return (self.position, self.intronic_position, self.utr, self.utr_position) == (
            other.position,
            other.intronic_position,
            other.utr,
            other.utr_position,
        )

    def __ne__(self, other: "VariantPosition") -> bool:
        """Not equal comparison operator.

        Other comparison operators will be filled in using :py:func:`functools.total_ordering`.

        Parameters
        ----------
        other : VariantPosition
            The other VariantPosition to compare to.

        Returns
        -------
        bool
            True if this position is not the same as the other position; else False.

        """
        return (self.position, self.intronic_position, self.utr, self.utr_position) != (
            other.position,
            other.intronic_position,
            other.utr,
            other.utr_position,
        )