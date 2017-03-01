# Copyright (C) 2001-2017 Andreas Lang-Nevyjel, init.at
#
# this file is part of icsw-client
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
""" simple database for the most common CPUs  """


from subprocess import getoutput
from initat.tools import logging_tools
from lxml import etree


class CPUId(object):
    def __init__(self, source: bytes=None, parse: bool=False):
        if source is None:
            of = getoutput("/opt/cluster/bin/lstopo-no-graphics --no-io --no-bridges --of xml").encode("utf-8")
            self.raw = of
        else:
            self.raw = source
        if parse:
            self.parse()

    def parse(self):
        _xml = etree.fromstring(self.raw)
        packages = []
        for _pack in _xml.findall(".//object[@type='Package']"):
            caches = {}
            cores = {}
            for _cache in _pack.findall(".//object[@type='Cache']"):
                core_idxs = [int(_core.attrib["os_index"]) for _core in _cache.findall(".//object[@type='Core']")]
                depth = int(_cache.attrib["depth"])
                size = int(_cache.attrib["cache_size"])
                cache_type = int(_cache.attrib["cache_type"])
                caches.setdefault(depth, {}).setdefault(cache_type, []).append((size, core_idxs))
                for core_idx in core_idxs:
                    cores.setdefault(core_idx, {}).setdefault(depth, {}).setdefault(cache_type, []).append(size)
            packages.append(
                {
                    "caches": caches,
                    "cores": cores,
                    "id": "{}.{}.{}".format(
                        _pack.find("info[@name='CPUFamilyNumber']").attrib["value"],
                        _pack.find("info[@name='CPUModelNumber']").attrib["value"],
                        _pack.find("info[@name='CPUStepping']").attrib["value"],
                    )
                }
            )
        self.packages = packages

    def get_core_info(self, package_idx, core_idx):
        _pack = self.packages[package_idx]
        _core = _pack["cores"][core_idx]
        size_f = []
        for _depth in sorted(_core.keys()):
            _size = sum(sum(_core[_depth].values(), []))
            size_f.append(logging_tools.get_size_str(_size, strip_spaces=True, to_int=True)[:-1].replace(" ", ""))
        return "{}_{}".format("".join(size_f), _pack["id"])

    @property
    def num_cores(self):
        return sum(len(_pack["cores"].keys()) for _pack in self.packages)


def get_cpuid():
    return "1_{}".format(CPUId(parse=True).get_core_info(0, 0))

# most likely source: http://www.softeng.rl.ac.uk/st/archive/SoftEng/SESP/html/SoftwareTools/vtune/
# users_guide/mergedProjects/analyzer_ec/mergedProjects/reference_olh/mergedProjects/instructions/instruct32_hh/vc46.htm
CPU_FLAG_LUT = {
    "FPU": "Floating Point Unit On-Chip. The processor contains an x87 FPU.",
    "VME": "Virtual 8086 Mode Enhancements. Virtual 8086 mode enhancements, including CR4.VME for controlling the feature, "
    "CR4.PVI for protected mode virtual interrupts, software interrupt indirection, expansion of the TSS with the software indirection bitmap, "
    "and EFLAGS.VIF and EFLAGS.VIP flags.",
    "DE": "Debugging Extensions. Support for I/O breakpoints, including CR4.DE for controlling the feature, and optional trapping of "
    "accesses to DR4 and DR5.",
    "PSE": "Page Size Extension. Large pages of size 4Mbyte are supported, including CR4.PSE for controlling the feature, the defined "
    "dirty bit in PDE (Page Directory Entries), optional reserved bit trapping in CR3, PDEs, and PTEs.",
    "TSC": "Time Stamp Counter. The RDTSC instruction is supported, including CR4.TSD for controlling privilege.",
    "MSR": "Model Specific Registers RDMSR and WRMSR Instructions. The RDMSR and WRMSR instructions are supported. Some of the MSRs "
    "are implementation dependent.",
    "PAE": "Physical Address Extension. Physical addresses greater than 32 bits are supported: extended page table entry formats, an "
    "extra level in the page translation tables is defined, 2 Mbyte pages are supported instead of 4 Mbyte pages if PAE bit is 1. "
    "The actual number of address bits beyond 32 is not defined, and is implementation specific.",
    "MCE": "Machine Check Exception. Exception 18 is defined for Machine Checks, including CR4.MCE for controlling the feature. This "
    "feature does not define the model-specific implementations of machine-check error logging, reporting, and processor shutdowns. Machine "
    "Check exception handlers may have to depend on processor version to do model specific processing of the exception, or test for the presence "
    "of the Machine Check feature.",
    "CX8": "CMPXCHG8B Instruction. The compare-and-exchange 8 bytes (64 bits) instruction is supported (implicitly locked and atomic).",
    "APIC": "APIC On-Chip. The processor contains an Advanced Programmable Interrupt Controller (APIC), responding to memory mapped commands in "
    "the physical address range FFFE0000H to FFFE0FFFH (by default - some processors permit the APIC to be relocated).",
    "SEP": "SYSENTER and SYSEXIT Instructions. The SYSENTER and SYSEXIT and associated MSRs are supported.",
    "MTRR": "Memory Type Range Registers. MTRRs are supported. The MTRRcap MSR contains feature bits that describe what memory types are supported, "
    "how many variable MTRRs are supported, and whether fixed MTRRs are supported.",
    "PGE": "PTE Global Bit. The global bit in page directory entries (PDEs) and page table entries (PTEs) is supported, indicating TLB entries that "
    "are common to different processes and need not be flushed. The CR4.PGE bit controls this feature.",
    "MCA": "Machine Check Architecture. The Machine Check Architecture, which provides a compatible mechanism for error reporting in P6 family, "
    "Pentium 4, and Intel Xeon processors is supported. The MCG_CAP MSR contains feature bits describing how many banks of error reporting MSRs "
    "are supported.",
    "CMOV": "Conditional Move Instructions. The conditional move instruction CMOV is supported. In addition, if x87 FPU is present as indicated by "
    "the CPUID.FPU feature bit, then the FCOMI and FCMOV instructions are supported.",
    "PAT": "Page Attribute Table. Page Attribute Table is supported. This feature augments the Memory Type Range Registers (MTRRs), allowing an "
    "operating system to specify attributes of memory on a 4K granularity through a linear address.",
    "PSE-36": "32-Bit Page Size Extension. Extended 4-MByte pages that are capable of addressing physical memory beyond 4 GBytes are supported. This "
    "feature indicates that the upper four bits of the physical address of the 4-MByte page is encoded by bits 13-16 of the page directory entry.",
    "PSN": "Processor Serial Number. The processor supports the 96-bit processor identification number feature and the feature is enabled.",
    "CLFLSH": "CLFLUSH Instruction. CLFLUSH Instruction is supported.",
    "DS": "Debug Store. The processor supports the ability to write debug information into a memory resident buffer. This feature is used by the "
    "branch trace store (BTS) and precise event-based sampling (PEBS) facilities (see Chapter 15, Debugging and Performance Monitoring, in the "
    "IA-32 Intel Architecture Software Developer's Manual, Volume 3).",
    "ACPI": "Thermal Monitor and Software Controlled Clock Facilities. The processor implements internal MSRs that allow processor temperature to "
    "be monitored and processor performance to be modulated in predefined duty cycles under software control.",
    "MMX": "Intel MMX Technology. The processor supports the Intel MMX technology.",
    "FXSR": "FXSAVE and FXRSTOR Instructions. The FXSAVE and FXRSTOR instructions are supported for fast save and restore of the floating point "
    "context. Presence of this bit also indicates that CR4.OSFXSR is available for an operating system to indicate that it supports the FXSAVE "
    "and FXRSTOR instructions.",
    "SSE": "SSE. The processor supports the SSE extensions.",
    "SSE2": "SSE2. The processor supports the SSE2 extensions.",
    "SS": "Self Snoop. The processor supports the management of conflicting memory types by performing a snoop of its own cache structure for "
    "transactions issued to the bus.",
    "HTT": "Hyper-Threading Technology. The processor implements Hyper-Threading technology.",
    "TM": "Thermal Monitor. The processor implements the thermal monitor automatic thermal control circuitry (TCC).",
    "PBE": "Pending Break Enable. The processor supports the use of the FERR#/PBE# pin when the processor is in the stop-clock state (STPCLK# is "
    "asserted) to signal the processor that an interrupt is pending and that the processor should return to normal operation to handle the interrupt. "
    "Bit 10 (PBE enable) in the IA32_MISC_ENABLE MSR enables this capability.",
}
