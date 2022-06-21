from sys import maxsize
from typing import (
    Any,
    Iterable,
    Optional,
    Union,
    List,
    Generator,
)

# from .language import Multiple


class StringCutter():
    @staticmethod
    def slice_by_wordcount(
        string: str,
        cut_at: int = 10,
        seperator: str = ' '
        ) -> List[List[str]]:
        """
        Devides string into multiple Lists with words with a given length.
        """
        string_list = [[]]

        [string_list[-1].append(word) 
        if len(string_list[-1]) < cut_at or not cut_at
        else string_list.append([word]) 
        for word in string.split(seperator)]

        return string_list

    @staticmethod
    def crumble(string: str,
        cut_at: int = 1900,
        seperator: str = ' ',
        clean_code: Any = False
        ) -> List[str]:
        """
        Crubles a string into a list with strings which have a given max length.
        """
        if clean_code:
            string.strip()

        sliced_list = __class__.slice_by_length(
            string=string,
            seperator=seperator,
            cut_at=cut_at
        )

        return ["".join(word for word in word_list)
        for word_list in sliced_list]

    @staticmethod
    def slice_by_length(
        string: Union[List[str], str],
        cut_at: int = 1900,
        seperator: str = ' '
    ) -> List[List[str]]:
        """
        Args:
        -----


        Returns:
        --------
        - (`List[List[str]]`) a list with sublists with strings. Sublist total
          stringlength <= cut_at.
        """

        list_length = 0
        word_list = []
        i = PeekIterator(string, seperator=seperator)

        while not i.eof:
            word_list.append([])
            list_length = 0
            if len(i.peek) > cut_at:
                raise WordToBig(
                    f'''Word in iterable was bigger ({len(i.peek)}) 
                    than the max given string lenth ({cut_at})'''
                )

            while ((list_length := list_length + len(i.peek)) <= cut_at 
                and not i.eof):
                word_list[-1].append(next(i))

        return word_list

class PeekIterator():
    """Iterator with 1 peak look ahead with peek atribute"""

    def __init__(self, 
        to_iter: Union[str, List[str]], 
        seperator: str = ' '
        ) -> None:
        if isinstance(to_iter, list):
            self._gen = (item if item else '' for item in to_iter)
        elif isinstance(to_iter, str):
            def generator(to_iter: str = to_iter, seperator: str = seperator) -> Generator[str, None, None]:
                for item in str(to_iter).split(seperator):
                    if not item:
                        yield ''
                    elif len(item) > 2000:
                        generator(item)
                    else:
                        yield item
            self._gen = generator()
            #self._gen = (f"{item}{seperator}" if item and len(item) < 2000 else '' if not item else sub_item if sub_item else '' for sub_item in crumble(item, 1980) for item in to_iter.split(seperator))
        
        self.peek = ''
        self.eof = False
        self._step()

    def __iter__(self):
        return self

    def __next__(self):
        peek = self.peek
        if self.eof:
            raise StopIteration()
        self._step()
        return peek

    def _step(self):
        try:
            self.peek: str = self._gen.__next__()
        except StopIteration:
            self.eof: bool = True

class SentenceInterator():
    """Returns strings with max size <max_size> intelligent splited."""

    def __init__(self, 
        to_iter: Union[str, List[str]], 
        max_size: int = 2000,
        ) -> None:
        if isinstance(to_iter, list):
            self._gen = (item if item else '' for item in to_iter)
        elif isinstance(to_iter, str):
            def generator(
                max_size:int = max_size,
                to_iter: str = to_iter,
            ) -> Generator[str, None, None]:
                """
                Iterates intelligent over the sentence

                Yields: Substrngs of this sentence
                
                """
                pos: int = 0
                symbols = ["\n\n\n", "\n\n", "\n", ";", ". ", "? ", "! ", ",", ") ", "} ", "] " ,": ", " ", ""]
                while pos + max_size < len(to_iter):
                    subitem = to_iter[pos:pos+max_size]
                    for symbol in symbols:
                        # nothing found -> look for lower prio symbol
                        if (
                            (occurence := subitem.rfind(symbol)) == -1
                            or occurence < max_size / 3 * 2
                        ):
                            
                            continue 
                        # smth found -> update pos, go to next substring
                        else:
                            # optimise if something paragraph like is detected - not necessary for code
                            # this will prevent from something like <title>\n\n\n<entry> whill be cutted after title
                            if (
                                ("\n" in symbol or "\n" == symbol)
                                # there is another \n in the string
                                and (sub_occurence := subitem[:occurence-len(symbol)].rfind("\n")) != -1
                                # other \n under the last 45 chars (these 45 are most likely the next paragraph headline)
                                and sub_occurence > len(subitem[:occurence-len(symbol)])-45
                            ):
                                # the suboccurence is not to short
                                if sub_occurence < occurence / 4 * 3:
                                    continue
                                # new phrase detected -> starting next iter with new phrase
                                yield subitem[:sub_occurence]
                                pos = pos + sub_occurence + len(symbol)
                                break
                            else:
                                yield subitem[:occurence+len(symbol)]
                                pos = pos + occurence + len(symbol)
                                break
                yield to_iter[pos:]

            self._gen = generator(
                to_iter=to_iter,
                max_size=max_size
            )
            #self._gen = (f"{item}{seperator}" if item and len(item) < 2000 else '' if not item else sub_item if sub_item else '' for sub_item in crumble(item, 1980) for item in to_iter.split(seperator))
        
        self.peek = ''
        self.eof = False
        self._step

    def __iter__(self):
        return self

    def __next__(self):
        # peek = self.peek
        # self._step()
        # return peek
        return self._gen.__next__()

    def _step(self):
        try:
            self.peek: str = self._gen.__next__()
        except StopIteration:
            self.eof: bool = True

class WordIterator:
    """
    ### Iterates through a string <`to_iter`> and returns word for word 
    """

    def __init__(self, 
        to_iter: str, 
    ) -> None:
        self.to_iter = to_iter
        self._gen = (word for word in to_iter.split(" "))

    def __iter__(self):
        return self

    def __next__(self):
        # don't return value instantly
        # add the removed whitespace for splitting to it
        return f"{self._gen.__next__()} "


class NumberWordIterator:
    """
    Iterator with 1 peak look ahead with peek atribute

    Example:
    -------
    "12.34House123 21bac12.12.12.12"
    >>> 12.34
    >>> House
    >>> 123
    >>> 21
    >>> bac
    >>> 12.12
    >>> 0.12
    >>> 0.12
    """

    def __init__(self, 
        to_iter: str, 
        ) -> None:
            self.to_iter = to_iter.lower()
            self._gen = (c for c in to_iter)
            self.eof = False
            try:
                self.peek_char = self._gen.__next__()
            except:
                self.eof = True
            self.peek_index = 1
            self.index = 0
            self.last_word_index = 0
            self.peek: str = ''

            self._step()
            

    def __next_incr(self) -> str:
        self.peek_char = self._gen.__next__()
        self.peek_index += 1
        return self.peek_char

    def __iter__(self):
        return self

    def __next__(self):
        peek = self.peek
        self.last_word_index = self.index
        self.index = self.peek_index
        self._step()
        if peek is None:
            raise StopIteration
        return peek

    def _next_number(self, prefix: str = "") -> float:
        number_chars = "1234567890-.,"
        number = prefix
        number = number.replace(",", ".")
        if "." in number:
            has_point = True
        else:
            has_point = False
        while self.peek_char in number_chars:
            if self.peek_char == " ":
                self.peek_char: str = self.__next_incr()
                break
            if self.peek_char == "-" and number != "":
                break
            if self.peek_char in ".,":
                if has_point:
                    break
                else:
                    number += self.peek_char
                    has_point = True
            else:
                number += self.peek_char
            try:
                self.peek_char: str = self.__next_incr()
            except StopIteration:
                self.eof = True
                break
        number = number.replace(",", ".")
        if number.startswith("."):
            number = f"0{number}"
        try:
            number = float(number)
        except Exception:
            raise RuntimeError(f"Can't parse `{number}` to float")
        return number

    def _next_word(self, prefix: str = "") -> str:
        number_chars = "1234567890"
        word = prefix
        while not self.peek_char in number_chars:
            if self.peek_char == " ":
                self.peek_char: str = self.__next_incr()
                break
            word += self.peek_char
            try:
                self.peek_char: str = self.__next_incr()
            except StopIteration:
                self.eof = True
                break
        return word

    def _step(self):
        number_chars = "1234567890"
        number_prefix = ".,-"
        if self.eof:
            self.peek = None
            return
        if self.peek_char in number_chars:
            self.peek = self._next_number()
        elif self.peek_char in number_prefix:
            peek = self.peek_char
            peek_peek = self.peek_char = self._gen.__next__()
            self.index += 1
            if peek_peek in number_chars:
                self.peek = self._next_number(prefix=peek)
            else:
                self.peek = self._next_word(prefix=peek)
        else:
            self.peek = self._next_word()

    


class WordToBig(Exception):
    """
    Raised, when word in iterator is bigger that allowd limit of string len.
    """
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)


    @staticmethod
    def slice_by_length(
        string: Union[List[str], str],
        cut_at: int = 1900,
        seperator: str = ' '
    ) -> List[List[str]]:
        """
        Args:
        -----
        string : `str`
            the string you want to cut into lists
        cut_at : `int`
            how long the partial strings should be
        seperator : `str`
            the seperator, where to cut the <string> if not list
 
        Returns:
        --------
        `List[str]` :
            a List with strings with max length <= `<cut_at>`
        """
        word_list = StringCutter.slice_by_length(
            string=string,
            cut_at=cut_at,
            seperator=seperator,
        )
        return [seperator.join(l) for l in word_list]

def crumble(
    string: str,
    max_length_per_string: int = 2000,
    seperator: Optional[str] = None,
    clean_code: bool = True,
    _autochange_seperator = True
    ) -> List[str]:
    """Splits a string into strings which length <= max_length is. If seperator is None, the SentenceIterator will be userd"""

    if clean_code:
        string = string.strip()

    if len(string) <= max_length_per_string:
        return [string]
    
    if seperator is None:
        return [part for part in SentenceInterator(string, max_length_per_string)]

    # some strings only have \n to seperate - not " "
    if seperator == " " and seperator not in string and _autochange_seperator:
        seperator = "\n"
    return StringCutter.crumble(
        string=string,
        cut_at=max_length_per_string,
        seperator=seperator,
        clean_code=clean_code,
    )

if __name__ == "__main__":
    VPN = """
Authentication

Tunnel endpoints must be authenticated before secure VPN tunnels can be established. User-created remote-access VPNs may use passwords, biometrics, two-factor authentication or other cryptographic methods. Network-to-network tunnels often use passwords or digital certificates. They permanently store the key to allow the tunnel to establish automatically, without intervention from the administrator.
Routing

Tunneling protocols can operate in a point-to-point network topology that would theoretically not be considered a VPN because a VPN by definition is expected to support arbitrary and changing sets of network nodes. But since most router implementations support a software-defined tunnel interface, customer-provisioned VPNs often are simply defined tunnels running conventional routing protocols.
Provider-provisioned VPN building-blocks
Site-to-Site VPN terminology.

Depending on whether a provider-provisioned VPN (PPVPN) operates in layer 2 or layer 3, the building blocks described below may be L2 only, L3 only, or a combination of both. Multi-protocol label switching (MPLS) functionality blurs the L2-L3 identity.[18][original research?]

RFC 4026 generalized the following terms to cover L2 MPLS VPNs and L3 (BGP) VPNs, but they were introduced in RFC 2547.[19][20]

Customer (C) devices

A device that is within a customer's network and not directly connected to the service provider's network. C devices are not aware of the VPN.

Customer Edge device (CE)

A device at the edge of the customer's network which provides access to the PPVPN. Sometimes it is just a demarcation point between provider and customer responsibility. Other providers allow customers to configure it.

Provider edge device (PE)

A device, or set of devices, at the edge of the provider network which connects to customer networks through CE devices and presents the provider's view of the customer site. PEs are aware of the VPNs that connect through them, and maintain VPN state.

Provider device (P)

A device that operates inside the provider's core network and does not directly interface to any customer endpoint. It might, for example, provide routing for many provider-operated tunnels that belong to different customers' PPVPNs. While the P device is a key part of implementing PPVPNs, it is not itself VPN-aware and does not maintain VPN state. Its principal role is allowing the service provider to scale its PPVPN offerings, for example, by acting as an aggregation point for multiple PEs. P-to-P connections, in such a role, often are high-capacity optical links between major locations of providers.
User-visible PPVPN services
OSI Layer 2 services

Virtual LAN

Virtual LAN (VLAN) is a Layer 2 technique that allows for the coexistence of multiple local area network (LAN) broadcast domains interconnected via trunks using the IEEE 802.1Q trunking protocol. Other trunking protocols have been used but have become obsolete, including Inter-Switch Link (ISL), IEEE 802.10 (originally a security protocol but a subset was introduced for trunking), and ATM LAN Emulation (LANE).

Virtual private LAN service (VPLS)

Developed by Institute of Electrical and Electronics Engineers, Virtual LANs (VLANs) allow multiple tagged LANs to share common trunking. VLANs frequently comprise only customer-owned facilities. Whereas VPLS as described in the above section (OSI Layer 1 services) supports emulation of both point-to-point and point-to-multipoint topologies, the method discussed here extends Layer 2 technologies such as 802.1d and 802.1q LAN trunking to run over transports such as Metro Ethernet.

As used in this context, a VPLS is a Layer 2 PPVPN, emulating the full functionality of a traditional LAN. From a user standpoint, a VPLS makes it possible to interconnect several LAN segments over a packet-switched, or optical, provider core, a core transparent to the user, making the remote LAN segments behave as one single LAN.[21]

In a VPLS, the provider network emulates a learning bridge, which optionally may include VLAN service.

Pseudo wire (PW)

PW is similar to VPLS, but it can provide different L2 protocols at both ends. Typically, its interface is a WAN protocol such as Asynchronous Transfer Mode or Frame Relay. In contrast, when aiming to provide the appearance of a LAN contiguous between two or more locations, the Virtual Private LAN service or IPLS would be appropriate.

Ethernet over IP tunneling

EtherIP (RFC 3378)[22] is an Ethernet over IP tunneling protocol specification. EtherIP has only packet encapsulation mechanism. It has no confidentiality nor message integrity protection. EtherIP was introduced in the FreeBSD network stack[23] and the SoftEther VPN[24] server program.

IP-only LAN-like service (IPLS)

A subset of VPLS, the CE devices must have Layer 3 capabilities; the IPLS presents packets rather than frames. It may support IPv4 or IPv6.
OSI Layer 3 PPVPN architectures

This section discusses the main architectures for PPVPNs, one where the PE disambiguates duplicate addresses in a single routing instance, and the other, virtual router, in which the PE contains a virtual router instance per VPN. The former approach, and its variants, have gained the most attention.

One of the challenges of PPVPNs involves different customers using the same address space, especially the IPv4 private address space.[25] The provider must be able to disambiguate overlapping addresses in the multiple customers' PPVPNs.

BGP/MPLS PPVPN

In the method defined by RFC 2547, BGP extensions advertise routes in the IPv4 VPN address family, which are of the form of 12-byte strings, beginning with an 8-byte route distinguisher (RD) and ending with a 4-byte IPv4 address. RDs disambiguate otherwise duplicate addresses in the same PE.

PEs understand the topology of each VPN, which are interconnected with MPLS tunnels either directly or via P routers. In MPLS terminology, the P routers are Label Switch Routers without awareness of VPNs.

Virtual router PPVPN

The virtual router architecture,[26][27] as opposed to BGP/MPLS techniques, requires no modification to existing routing protocols such as BGP. By the provisioning of logically independent routing domains, the customer operating a VPN is completely responsible for the address space. In the various MPLS tunnels, the different PPVPNs are disambiguated by their label but do not need routing distinguishers.
Unencrypted tunnels

Some virtual networks use tunneling protocols without encryption for protecting the privacy of data. While VPNs often do provide security, an unencrypted overlay network does not neatly fit within the secure or trusted categorization.[28] For example, a tunnel set up between two hosts with Generic Routing Encapsulation (GRE) is a virtual private network but is neither secure nor trusted.[29][30]

Native plaintext tunneling protocols include Layer 2 Tunneling Protocol (L2TP) when it is set up without IPsec and Point-to-Point Tunneling Protocol (PPTP) or Microsoft Point-to-Point Encryption (MPPE).[31] 
    """
    # for item in SentenceInterator(to_iter = VPN, max_size = 1900):
    #     print(item, len(item))
    #     x = input()

if __name__ == "__main__":
    strs = crumble(str("q \n\n\n\n qqqqqqqqqqqq fsldf; " * 10000), 2000)
    [print(len(s)) for s in strs]
