---
title: "Dissicting the 82559 Ethernet controller - From bits to waves"
date: "2012-05-09T13:57:00Z"
lastmod: "2025-05-14T06:34:16Z"
slug: "from-bits-to-waves-the-inner-workings-of-an-ethernet-controller"
description: "When I first started working, I was very interested in learning about the Linux kernel. Specifically the TCP/IP stack and the inner workings of an Ethernet controller. To learn more, I picked one of the most widely used Ethernet…"
summary: "When I first started working, I was very interested in learning about the Linux kernel. Specifically the TCP/IP stack and the inner workings of an Ethernet controller. To learn more, I picked one of the most widely used Ethernet controllers at that time, the [Intel 82559 10/100 Fast Ethernet Controller](http://www.intel.com/design/network/products/lan/controllers/82559.htm \"Intel 82559 10/100 Fast Ethernet Controller\") and one of its open-source drivers, the [eepro100](http://lxr.free-electrons.com/source/drivers/net/eepro100.c?v=2.4.37).\n\nThought 82559 chip is no longer manufactured and the eepro driver has been deprecated, this article will still serve as a guide for how an ethernet controller works. We'll look at how the eepro100 driver interfaces with the Intel 82559 chipset and how the 82559 converts the packets sent by the driver to signals transmitted over physical ethernet cable."
image: "/wp-content/uploads/2012/05/Deepak-Kandepet-Image.gif"
categories:
  - "internals"
  - "teardown"
---

When I first started working, I was very interested in learning about the Linux kernel. Specifically the TCP/IP stack and the inner workings of an Ethernet controller. To learn more, I picked one of the most widely used Ethernet controllers at that time, the [Intel 82559 10/100 Fast Ethernet Controller](http://www.intel.com/design/network/products/lan/controllers/82559.htm "Intel 82559 10/100 Fast Ethernet Controller") and one of its open-source drivers, the [eepro100](http://lxr.free-electrons.com/source/drivers/net/eepro100.c?v=2.4.37).

Thought 82559 chip is no longer manufactured and the eepro driver has been deprecated, this article will still serve as a guide for how an ethernet controller works. We'll look at how the eepro100 driver interfaces with the Intel 82559 chipset and how the 82559 converts the packets sent by the driver to signals transmitted over physical ethernet cable.

## The mighty 82559

The 82559 is an Intel ethernet chipset. It supports 10/100 Mbps full duplex data communication over a pair of wires. This is a high level block diagram of the 82559.

![](/images/external/i.imgur.com/Hrya0jc.png)

The most important subsystems of 82559 are:

- A parallel subsystem (shown in green).
- A FIFO subsystem (shown in red).
- The 10/100 Mbps Carrier Sense Multiple Access with Collision Detect (CSMA/CD) unit (shown in blue).
- The 10/100 Mbps physical layer (PHY) unit (shown in black).

### The parallel subsystem

The parallel subsystem is responsible for interfacing the chipset with the motherboard via the PCI bus. It also controls and executes all the chipset's functions via a Micro-Machine.

As a PCI device, 82559 can operate in two modes:

- As a PCI target (slave mode). In slave mode, 82559 is completely controlled by the host CPU. The CPU initiates all transmit and receive actions when 82559 is in slave mode.
- For processing the transmit and receive frames, the 82559 operates as a master on the PCI bus. It needs no help from the host CPU to read/write memory or other resources and can work independently.

The **micromachine** is an embedded processing unit. Instructions for carrying out all the 82559's functions are embedded in a microcode ROM within the micromachine. The micromachine is divided into two units:

- **Receive Unit (RU)**
- **Command Unit (CU)**. The CU is also the transmit unit.

These two units operate independently and concurrently. Control is switched between the two units according to the microcode instruction flow. The independence of the Receive and Command units in the micromachine allows the 82559 to execute commands and receive incoming frames simultaneously, with no real-time CPU intervention.

The 82559 also interfaces with an external Flash memory and an external serial EEPROM. The **Flash memory** may be used for remote boot functions, network statistics, diagnostics and management functions. The **EEPROM** is used to store relevant information for a LAN connection such as node address (MAC Address), as well as board manufacturing and configuration information.

### FIFO Subsystem

The 82559 FIFO (First In, First Out) subsystem consists of a 3 Kbyte transmit FIFO and 3 Kbyte receive FIFO. Each FIFO is unidirectional and independent of the other. The FIFO subsystem serves as the interface between the 82559 parallel side and the serial CSMA/CD unit. It provides a temporary buffer storage area for frames as they are either being received or transmitted by the 82559. Transmit frames can be queued within the transmit FIFO, allowing back-to-back transmission within the [minimum Interframe Spacing (IFS)](http://en.wikipedia.org/wiki/Interframe_gap "Interframe gap"). Transmissions resulting in errors (collision detection or data underruns) are re-transmitted directly from the 82559 FIFO eliminating the need to re-access this data from the host system.

### CSMA/CD unit

The CSMA/CD unit of the 82559 allows it to be connected to either a 10 or 100 Mbps Ethernet network. The CSMA/CD unit performs all of the functions of the 802.3 protocol such as [frame formatting, frame stripping, collision handling, deferral to link traffic](http://en.wikipedia.org/wiki/CSMA/CD "CSMA/CD"), etc. The CSMA/CD unit can also be placed in a full duplex mode which allows simultaneous transmission and reception of frames.

### Physical Unit (PHY)

The [Physical Layer (PHY)](http://en.wikipedia.org/wiki/PHY_%28chip%29 "PHY Layer") unit of the 82559 is where the digital data is converted to a signal that can propagate over the network wires. To make the actual connection to the network, additional components such as transformers and impedances are needed. This additional components are external to 82559.

## Accessing 82559 as a PCI device

A PCI peripheral boards can be accessed using three different address spaces: memory locations, I/O ports, and configuration registers.

- The memory and I/O port address space is shared by all devices on a PCI bus (i.e., when you access a memory location, all the devices see the bus cycle at the same time). A driver can read memory and I/O regions via inb, readb, and so forth.
- The configuration space, on the other hand, exploits geographical addressing. i.e. each PCI slot is uniquely addressed (by a 16 bit address), thus eliminating collisions when configuring devices. To access the configuration space of 82559, the full configuration address (bus, slot, function, offset) is written to an I/O port (for 82559, CONFIG\_ADDRESS = 0xCF8) and then the 32-bit word at this address can be read or written through another location (for 82559, CONFIG\_DATA = 0xCFC ).

After a PCI device is powered on, the hardware remains in an inactive state and the will only respond to configuration transactions. This is because, at power on, the device does not have its memory and I/O ports mapped into the computer's address space. Every other device-specific feature, such as interrupt reporting, is disabled as well.

After power on, the BIOS must first scan the PCI bus to determine what PCI device exists and what configuration requirements they have. In order to facilitate this process, all PCI devices, including 82559, must implement a base set of configuration registers as defined by the PCe standard. Registers defined by 82559 is shown in the figure below.

![](/images/external/i.imgur.com/sAubaXX.jpg)

The BIOS reads the Vendor ID, Device ID and Class registers in order to detect the device and its type. 82559 being an Intel device, returns a hard-coded 8086H for Device ID.

### Memory & IO Mapping the 82559 device.

Having detected 82559, the BIOS then accesses 82559's base address configuration registers to determine how many blocks of memory and/or IO space the device requires. Base Address Register (BAR) is 32 bits wide and there can be upto 6 BARs per device. 82559 defines 3 types of BARs, the Control/Status Registers (CSR), Flash, and Expansion ROM as shown in figure above.

![](/images/external/i.imgur.com/j7F86Ke.jpg)

Bit zero in all base registers is read only and is used to determine whether the register maps into memory (0) or I/O space (1). Figure above shows the layout of a BAR for memory mapping.

The 82559 contains three BARs, two requesting memory mapped resources and one requesting IO mapping. Specifically, Control and Status Register (CSR) is both Memory Mapped (CSR Memory mapped base address register: 10H) and IO mapped (CSR I/O Mapped Base Address Register: 14H) to anywhere within the 32-bit memory address space. It is up to the driver (eepro100) to determine which BAR (I/O or Memory) to use to access the 82559 Control/Status registers. The size of the memory space is 4Kb and that of I/O space is 32 bytes. The 82559 also requires one BAR (Flash Memory Mapped Base Address Register: 18H) to map accesses to an optional FLASH memory.

After determining the types of mapping and amount of memory/IO space requested from the BARs, BIOS maps the I/O and memory controllers into available memory locations and proceeds with system boot.

## The Kernel PCI Initialization

As described above, for Intel based systems, the system BIOS which ran at boot time has already fully configured the PCI system. This leaves Linux kernel with little to do other than remap that configuration.

The PCI device driver (pci.c) starts by scanning PCI Buses and creates a *pci\_dev* for every device (including PCI-to-PCI bridges) and *pci\_bus* for every bus it finds. These structures are linked together into a tree that mimics the actual PCI topology.

![](/images/external/i.imgur.com/5FekSFZ.jpg)

At this stage, the BIOS has recognized the 82559 and configured its PCI configuration space assigning it unique memory and IO space and the Linux kernel has created a *pci\_dev* data structure defining 82559.

## 82559 PCI Initialization

When the eepro100 driver module is loaded into the kernel, the driver registers itself as a PCI driver by calling *pci\_register\_driver()*. Implicitly passed to *pci\_register\_driver()* is a table of all supported devices (*eepro100\_pci\_tbl*). This table lists all the chipsets this driver is capable of driving: 82557, 82558, 82559, 82801, etc.

```
2371 
2372 static struct pci_device_id eepro100_pci_tbl[] __devinitdata = {
2373         { PCI_VENDOR_ID_INTEL, PCI_DEVICE_ID_INTEL_82557,
2374                 PCI_ANY_ID, PCI_ANY_ID, },
2375         { PCI_VENDOR_ID_INTEL, PCI_DEVICE_ID_INTEL_82559ER,
2376                 PCI_ANY_ID, PCI_ANY_ID, },
2377         { PCI_VENDOR_ID_INTEL, PCI_DEVICE_ID_INTEL_82801BA_7,
2378                 PCI_ANY_ID, PCI_ANY_ID, },
2379         { PCI_VENDOR_ID_INTEL, 0x1029, PCI_ANY_ID, PCI_ANY_ID, },
2380         { PCI_VENDOR_ID_INTEL, 0x1030, PCI_ANY_ID, PCI_ANY_ID, },
2381         { PCI_VENDOR_ID_INTEL, 0x1031, PCI_ANY_ID, PCI_ANY_ID, },
2382         { PCI_VENDOR_ID_INTEL, 0x1032, PCI_ANY_ID, PCI_ANY_ID, },
2383         { PCI_VENDOR_ID_INTEL, 0x1033, PCI_ANY_ID, PCI_ANY_ID, },
2384         { PCI_VENDOR_ID_INTEL, 0x1034, PCI_ANY_ID, PCI_ANY_ID, },
2385         { PCI_VENDOR_ID_INTEL, 0x1035, PCI_ANY_ID, PCI_ANY_ID, },
2386         { PCI_VENDOR_ID_INTEL, 0x1036, PCI_ANY_ID, PCI_ANY_ID, },
2387         { PCI_VENDOR_ID_INTEL, 0x1037, PCI_ANY_ID, PCI_ANY_ID, },
2388         { PCI_VENDOR_ID_INTEL, 0x1038, PCI_ANY_ID, PCI_ANY_ID, },
2389         { PCI_VENDOR_ID_INTEL, 0x1039, PCI_ANY_ID, PCI_ANY_ID, },
2390         { PCI_VENDOR_ID_INTEL, 0x103A, PCI_ANY_ID, PCI_ANY_ID, },
2391         { PCI_VENDOR_ID_INTEL, 0x103B, PCI_ANY_ID, PCI_ANY_ID, },
2392         { PCI_VENDOR_ID_INTEL, 0x103C, PCI_ANY_ID, PCI_ANY_ID, },
2393         { PCI_VENDOR_ID_INTEL, 0x103D, PCI_ANY_ID, PCI_ANY_ID, },
2394         { PCI_VENDOR_ID_INTEL, 0x103E, PCI_ANY_ID, PCI_ANY_ID, },
2395         { PCI_VENDOR_ID_INTEL, 0x1050, PCI_ANY_ID, PCI_ANY_ID, },
2396         { PCI_VENDOR_ID_INTEL, 0x1059, PCI_ANY_ID, PCI_ANY_ID, },
2397         { PCI_VENDOR_ID_INTEL, 0x1227, PCI_ANY_ID, PCI_ANY_ID, },
2398         { PCI_VENDOR_ID_INTEL, 0x1228, PCI_ANY_ID, PCI_ANY_ID, },
2399         { PCI_VENDOR_ID_INTEL, 0x2449, PCI_ANY_ID, PCI_ANY_ID, },
2400         { PCI_VENDOR_ID_INTEL, 0x2459, PCI_ANY_ID, PCI_ANY_ID, },
2401         { PCI_VENDOR_ID_INTEL, 0x245D, PCI_ANY_ID, PCI_ANY_ID, },
2402         { PCI_VENDOR_ID_INTEL, 0x5200, PCI_ANY_ID, PCI_ANY_ID, },
2403         { PCI_VENDOR_ID_INTEL, 0x5201, PCI_ANY_ID, PCI_ANY_ID, },
2404         { 0,}
2405 };
2406 MODULE_DEVICE_TABLE(pci, eepro100_pci_tbl);
```

{{< gist 3837669 >}}

After registering the driver, *pci\_register\_driver()* probes [*pci\_device\_probe()*] the PCI device tree for all unclaimed PCI devices. Chances are that one of those devices could be an eepro100 compatible device. When an unclaimed device is found, *pci\_bus\_match()* and *pci\_match\_device()* are called to check if this unclaimed device is an eepro100 compliant PCI device.

*pci\_match\_device()* checks if the PCI\_VENDOR\_ID, PCI\_DEVICE\_ID, PCI\_SUBVENDOR\_ID, PCI\_SUBDEVICE\_ID from the *eepro100\_pci\_tbl* and the device configure header values match (see 82559 configuration space figure above). If a match is found, eepro100's probe function, *eepro100\_init\_one()*, is called to reset/probe the new device. After the probe is complete, the device is marked as claimed by eepro100.

```
579 static int __devinit eepro100_init_one (struct pci_dev *pdev,
580                 const struct pci_device_id *ent)
581 {
582         unsigned long ioaddr;
583         int irq;
584         int acpi_idle_state = 0, pm;
585         static int cards_found /* = 0 */;
586
587 #ifndef MODULE
588         /* when built-in, we only print version if device is found */
589         static int did_version;
590         if (did_version++ == 0)
591                 printk(version);
592 #endif
593
594         /* save power state before pci_enable_device overwrites it */
595         pm = pci_find_capability(pdev, PCI_CAP_ID_PM);
596         if (pm) {
597                 u16 pwr_command;
598                 pci_read_config_word(pdev, pm + PCI_PM_CTRL, &pwr_command);
599                 acpi_idle_state = pwr_command & PCI_PM_CTRL_STATE_MASK;
600         }
601
602         if (pci_enable_device(pdev))
603                 goto err_out_free_mmio_region;
604
605         pci_set_master(pdev);
606
607         if (!request_region(pci_resource_start(pdev, 1),
608                         pci_resource_len(pdev, 1), "eepro100")) {
609                 printk (KERN_ERR "eepro100: cannot reserve I/O ports\n");
610                 goto err_out_none;
611         }
612         if (!request_mem_region(pci_resource_start(pdev, 0),
613                         pci_resource_len(pdev, 0), "eepro100")) {
614                 printk (KERN_ERR "eepro100: cannot reserve MMIO region\n");
615                 goto err_out_free_pio_region;
616         }
617
618         irq = pdev->irq;
619 #ifdef USE_IO
620         ioaddr = pci_resource_start(pdev, 1);
621         if (DEBUG & NETIF_MSG_PROBE)
622                 printk("Found Intel i82557 PCI Speedo at I/O %#lx, IRQ %d.\n",
623                            ioaddr, irq);
624 #else
625         ioaddr = (unsigned long)ioremap(pci_resource_start(pdev, 0),
626                                                                         pci_resource_len(pdev, 0));
627         if (!ioaddr) {
628                 printk (KERN_ERR "eepro100: cannot remap MMIO region %lx @ %lx\n",
629                                 pci_resource_len(pdev, 0), pci_resource_start(pdev, 0));
630                 goto err_out_free_mmio_region;
631         }
632         if (DEBUG & NETIF_MSG_PROBE)
633                 printk("Found Intel i82557 PCI Speedo, MMIO at %#lx, IRQ %d.\n",
634                            pci_resource_start(pdev, 0), irq);
635 #endif
636
637
638         if (speedo_found1(pdev, ioaddr, cards_found, acpi_idle_state) == 0)
639                 cards_found++;
640         else
641                 goto err_out_iounmap;
642
643         return 0;
644
645 err_out_iounmap: ;
646 #ifndef USE_IO
647         iounmap ((void *)ioaddr);
648 #endif
649 err_out_free_mmio_region:
650         release_mem_region(pci_resource_start(pdev, 0), pci_resource_len(pdev, 0));
651 err_out_free_pio_region:
652         release_region(pci_resource_start(pdev, 1), pci_resource_len(pdev, 1));
653 err_out_none:
654         return -ENODEV;
655 }
```

*pci\_find\_capability()*: Every device that supports PCI power management, including 82559, has an 8 byte capability field in its PCI configuration space (See address DCh - Eoh in the figure above). This field is used to describe and control the standard PCI power management features. The PCI PM spec defines 4 operating states for devices, D0 - D3. The higher the number, less power the device consumes but longer is the latency for the device to return to the operational state (D0). 82559 supports all 4 power states. *pci\_enable\_device()* (via *pci\_set\_power\_state()*) activates 82559 by switching it to the D0 state.

*pci\_set\_master()*: If the device has bus mastering capability, during bootup the BIOS can read two of its configuration registers (Minimum Grant register: Min\_Gnt and Maximum Latency register: Max\_Lat, see configuration registers in the above figure) to determine how quickly it requires access to the PCI bus when it asserts REQ# pin and the average duration of its transfer when it has acquired ownership of the bus. The BIOS can utilize this information to program the bus master's latency timer register and the PCI bus arbiter to provide the optimum PCI bus utilization. For 82559, the default value of Minimum Grant Register is 08H and Maximum Latency Register is 18H. pci\_set\_master() is called to enable 82559 to act as a bus master.

During boot, the BIOS had allocated a range of unique memory and IO regions for accessing 82559's configuration space. For the driver to use these regions, they have to be reserved and locked in the kernel by marking those regions as BUSY (to prevent other drivers from accessing these same regions). *eepro100\_init\_one()* locks the PCI BIOS assigned IO port regions using *request\_region()* (cat /proc/ioports to see a list of all locked IO ports). Similarly to reserve memory mapped regions *request\_mem\_region()* is called. This is done for all the 3 regions pointed to by the 3 active 82559 BARs.

The 82559 is now physically enabled and is ready to start receiving and transmitting ethernet frames. The driver now prepares the kernel to start using this device for network access via *speedo\_found1()*.

```
657 static int __devinit speedo_found1(struct pci_dev *pdev,
658                 long ioaddr, int card_idx, int acpi_idle_state)
659 {
660         struct net_device *dev;
661         struct speedo_private *sp;
662         const char *product;
663         int i, option;
664         u16 eeprom[0x100];
665         int size;
666         void *tx_ring_space;
667         dma_addr_t tx_ring_dma;
668
669         size = TX_RING_SIZE * sizeof(struct TxFD) + sizeof(struct speedo_stats);
670         tx_ring_space = pci_alloc_consistent(pdev, size, &tx_ring_dma);
671         if (tx_ring_space == NULL)
672                 return -1;
673
674         dev = init_etherdev(NULL, sizeof(struct speedo_private));
675         if (dev == NULL) {
676                 printk(KERN_ERR "eepro100: Could not allocate ethernet device.\n");
677                 pci_free_consistent(pdev, size, tx_ring_space, tx_ring_dma);
678                 return -1;
679         }
680
681         SET_MODULE_OWNER(dev);
682
683         if (dev->mem_start > 0)
684                 option = dev->mem_start;
685         else if (card_idx >= 0  &&  options[card_idx] >= 0)
686                 option = options[card_idx];
687         else
688                 option = 0;
689
690         /* Read the station address EEPROM before doing the reset.
691            Nominally his should even be done before accepting the device, but
692            then we wouldn't have a device name with which to report the error.
693            The size test is for 6 bit vs. 8 bit address serial EEPROMs.
694         */
695         {
696                 unsigned long iobase;
697                 int read_cmd, ee_size;
698                 u16 sum;
699                 int j;
700
701                 /* Use IO only to avoid postponed writes and satisfy EEPROM timing
702                    requirements. */
703                 iobase = pci_resource_start(pdev, 1);
704                 if ((do_eeprom_cmd(iobase, EE_READ_CMD << 24, 27) & 0xffe0000)
705                         == 0xffe0000) {
706                         ee_size = 0x100;
707                         read_cmd = EE_READ_CMD << 24;
708                 } else {
709                         ee_size = 0x40;
710                         read_cmd = EE_READ_CMD << 22;
711                 }
712
713                 for (j = 0, i = 0, sum = 0; i < ee_size; i++) {
714                         u16 value = do_eeprom_cmd(iobase, read_cmd | (i << 16), 27);
715                         eeprom[i] = value;
716                         sum += value;
717                         if (i < 3) {
718                                 dev->dev_addr[j++] = value;
719                                 dev->dev_addr[j++] = value >> 8;
720                         }
721                 }
722                 if (sum != 0xBABA)
723                         printk(KERN_WARNING "%s: Invalid EEPROM checksum %#4.4x, "
724                                    "check settings before activating this device!\n",
725                                    dev->name, sum);
726                 /* Don't  unregister_netdev(dev);  as the EEPro may actually be
727                    usable, especially if the MAC address is set later.
728                    On the other hand, it may be unusable if MDI data is corrupted. */
729         }
730
731         /* Reset the chip: stop Tx and Rx processes and clear counters.
732            This takes less than 10usec and will easily finish before the next
733            action. */
734         outl(PortReset, ioaddr + SCBPort);
735         inl(ioaddr + SCBPort);
736         udelay(10);
737
738         if (eeprom[3] & 0x0100)
739                 product = "OEM i82557/i82558 10/100 Ethernet";
740         else
741                 product = pdev->name;
742
743         printk(KERN_INFO "%s: %s, ", dev->name, product);
744
745         for (i = 0; i < 5; i++)
746                 printk("%2.2X:", dev->dev_addr[i]);
747         printk("%2.2X, ", dev->dev_addr[i]);
748 #ifdef USE_IO
749         printk("I/O at %#3lx, ", ioaddr);
750 #endif
751         printk("IRQ %d.\n", pdev->irq);
752
753         /* we must initialize base_addr early, for mdio_{read,write} */
754         dev->base_addr = ioaddr;
755
756 #if 1 || defined(kernel_bloat)
757         /* OK, this is pure kernel bloat.  I don't like it when other drivers
758            waste non-pageable kernel space to emit similar messages, but I need
759            them for bug reports. */
760         {
761                 const char *connectors[] = {" RJ45", " BNC", " AUI", " MII"};
762                 /* The self-test results must be paragraph aligned. */
763                 volatile s32 *self_test_results;
764                 int boguscnt = 16000;   /* Timeout for set-test. */
765                 if ((eeprom[3] & 0x03) != 0x03)
766                         printk(KERN_INFO "  Receiver lock-up bug exists -- enabling"
767                                    " work-around.\n");
768                 printk(KERN_INFO "  Board assembly %4.4x%2.2x-%3.3d, Physical"
769                            " connectors present:",
770                            eeprom[8], eeprom[9]>>8, eeprom[9] & 0xff);
771                 for (i = 0; i < 4; i++)
772                         if (eeprom[5] & (1<<i))
773                                 printk(connectors[i]);
774                 printk("\n"KERN_INFO"  Primary interface chip %s PHY #%d.\n",
775                            phys[(eeprom[6]>>8)&15], eeprom[6] & 0x1f);
776                 if (eeprom[7] & 0x0700)
777                         printk(KERN_INFO "    Secondary interface chip %s.\n",
778                                    phys[(eeprom[7]>>8)&7]);
779                 if (((eeprom[6]>>8) & 0x3f) == DP83840
780                         ||  ((eeprom[6]>>8) & 0x3f) == DP83840A) {
781                         int mdi_reg23 = mdio_read(dev, eeprom[6] & 0x1f, 23) | 0x0422;
782                         if (congenb)
783                           mdi_reg23 |= 0x0100;
784                         printk(KERN_INFO"  DP83840 specific setup, setting register 23 to %4.4x.\n",
785                                    mdi_reg23);
786                         mdio_write(dev, eeprom[6] & 0x1f, 23, mdi_reg23);
787                 }
788                 if ((option >= 0) && (option & 0x70)) {
789                         printk(KERN_INFO "  Forcing %dMbs %s-duplex operation.\n",
790                                    (option & 0x20 ? 100 : 10),
791                                    (option & 0x10 ? "full" : "half"));
792                         mdio_write(dev, eeprom[6] & 0x1f, MII_BMCR,
793                                            ((option & 0x20) ? 0x2000 : 0) |     /* 100mbps? */
794                                            ((option & 0x10) ? 0x0100 : 0)); /* Full duplex? */
795                 }
796
797                 /* Perform a system self-test. */
798                 self_test_results = (s32*) ((((long) tx_ring_space) + 15) & ~0xf);
799                 self_test_results[0] = 0;
800                 self_test_results[1] = -1;
801                 outl(tx_ring_dma | PortSelfTest, ioaddr + SCBPort);
802                 do {
803                         udelay(10);
804                 } while (self_test_results[1] == -1  &&  --boguscnt >= 0);
805
806                 if (boguscnt < 0) {             /* Test optimized out. */
807                         printk(KERN_ERR "Self test failed, status %8.8x:\n"
808                                    KERN_ERR " Failure to initialize the i82557.\n"
809                                    KERN_ERR " Verify that the card is a bus-master"
810                                    " capable slot.\n",
811                                    self_test_results[1]);
812                 } else
813                         printk(KERN_INFO "  General self-test: %s.\n"
814                                    KERN_INFO "  Serial sub-system self-test: %s.\n"
815                                    KERN_INFO "  Internal registers self-test: %s.\n"
816                                    KERN_INFO "  ROM checksum self-test: %s (%#8.8x).\n",
817                                    self_test_results[1] & 0x1000 ? "failed" : "passed",
818                                    self_test_results[1] & 0x0020 ? "failed" : "passed",
819                                    self_test_results[1] & 0x0008 ? "failed" : "passed",
820                                    self_test_results[1] & 0x0004 ? "failed" : "passed",
821                                    self_test_results[0]);
822         }
823 #endif  /* kernel_bloat */
824
825         outl(PortReset, ioaddr + SCBPort);
826         inl(ioaddr + SCBPort);
827         udelay(10);
828
829         /* Return the chip to its original power state. */
830         pci_set_power_state(pdev, acpi_idle_state);
831
832         pci_set_drvdata (pdev, dev);
833
834         dev->irq = pdev->irq;
835
836         sp = dev->priv;
837         sp->pdev = pdev;
838         sp->msg_enable = DEBUG;
839         sp->acpi_pwr = acpi_idle_state;
840         sp->tx_ring = tx_ring_space;
841         sp->tx_ring_dma = tx_ring_dma;
842         sp->lstats = (struct speedo_stats *)(sp->tx_ring + TX_RING_SIZE);
843         sp->lstats_dma = TX_RING_ELEM_DMA(sp, TX_RING_SIZE);
844         init_timer(&sp->timer); /* used in ioctl() */
845         spin_lock_init(&sp->lock);
846
847         sp->mii_if.full_duplex = option >= 0 && (option & 0x10) ? 1 : 0;
848         if (card_idx >= 0) {
849                 if (full_duplex[card_idx] >= 0)
850                         sp->mii_if.full_duplex = full_duplex[card_idx];
851         }
852         sp->default_port = option >= 0 ? (option & 0x0f) : 0;
853
854         sp->phy[0] = eeprom[6];
855         sp->phy[1] = eeprom[7];
856
857         sp->mii_if.phy_id = eeprom[6] & 0x1f;
858         sp->mii_if.phy_id_mask = 0x1f;
859         sp->mii_if.reg_num_mask = 0x1f;
860         sp->mii_if.dev = dev;
861         sp->mii_if.mdio_read = mdio_read;
862         sp->mii_if.mdio_write = mdio_write;
863
864         sp->rx_bug = (eeprom[3] & 0x03) == 3 ? 0 : 1;
865         if (((pdev->device > 0x1030 && (pdev->device < 0x103F)))
866             || (pdev->device == 0x2449) || (pdev->device == 0x2459)
867             || (pdev->device == 0x245D)) {
868                 sp->chip_id = 1;
869         }
870
871         if (sp->rx_bug)
872                 printk(KERN_INFO "  Receiver lock-up workaround activated.\n");
873
874         /* The Speedo-specific entries in the device structure. */
875         dev->open = &speedo_open;
876         dev->hard_start_xmit = &speedo_start_xmit;
877         netif_set_tx_timeout(dev, &speedo_tx_timeout, TX_TIMEOUT);
878         dev->stop = &speedo_close;
879         dev->get_stats = &speedo_get_stats;
880         dev->set_multicast_list = &set_rx_mode;
881         dev->do_ioctl = &speedo_ioctl;
882
883         return 0;
884 }
```

*speedo\_found1()*: The kernel needs to know that this is an Ethernet device and it can use this new PCI device to send/receive data over the network. For this, a device specific structure, *net\_device*, is create and registered *register\_netdevice()* with the kernel. *net\_device* contains the device name, it's MAC address, options like full-duplex, interrupt number (IRQ) & pointers to functions for executing all the device functions.

Every ethernet device found should have a unique name and on linux, ethernet devices are named eth0, eth1...eth100. *dev\_alloc\_name()* allocates a name for this device and sets it in *net\_device* structure.

Every 802.3 device has an unique 48-bit MAC address assigned to it. This address is not hardcoded in 82559, but is stored by the board manufacturer in a non-volatile form, such as in the EEPROM or Flash EPROM outside 82559.

82559 expects the EEPROM format to be as shown below.

![](/images/external/i.imgur.com/iS1xBwl.jpg)

The 82559 automatically reads five words (0H, 1H, 2H, AH, and DH) from the EEPROM during bootup. The MAC address is extracted from 0H, 1H & 2H. The rest of the EEPROM map contains device options like type of connector, the device type, PHY device ID etc.

*speedo\_found1()* then proceeds to reset the 82559 chip using the PORT command (writing a zero value to the SCBport, offset 8 in the CSR). The PORT commands is also used to self-test the 82559.

The kernel also needs to know what functions to call to open the device (*speedo\_open*), transmit (*speedo\_start\_xmit*), close/stop (*speedo\_stop*), get stats (*speedo\_get\_stats*), do IOCTL (*speedo\_ioctl*). Notice that there is no receive function. This is because packets are received asynchronously. When a new packet is received 82559 interrupts the kernel and the interrupt service routine handles the received packet (more on this later). At this point the timer routines are also initialized.

This completes the initialization of 82559. The device is now ready to receive & transmitt ethernet frames.

## Assigning an IP address to the device

After initializing the device, the device should be opened so that it is accessible from the IP layer. The device is accessible from the outside world when an IP address is assigned to it. One way to assign an IP address to an interface is throught the ifconfig program available from the *net-utils*.

The syntax to enable the device is:

*ifconfig eth0 up*

When asked to bring up the eth0 interface, ifconfig creates a generic raw TCP socket to the *afinet* address family and issues a *SIOCSIFFLAG* ioctl to this raw socket. The flags set on the interface are the IFF\_UP & IFF\_RUNNING.

```
/* ifconfig.c */

if (!strcmp(*spp, "up")) { goterr |= set_flag(ifr.ifr_name, (IFF_UP | IFF_RUNNING)); spp++; continue; }

/* Set a certain interface flag. */ static int set_flag(char *ifname, short flag) { struct ifreq ifr;

    safe_strncpy(ifr.ifr_name, ifname, IFNAMSIZ);
    if (ioctl(skfd, SIOCGIFFLAGS, &amp;ifr) &lt; 0) {
        fprintf(stderr, _("%s: unknown interface: %s\n"),
                ifname, strerror(errno));
        return (-1);
    }
    safe_strncpy(ifr.ifr_name, ifname, IFNAMSIZ);
    ifr.ifr_flags |= flag;
    if (ioctl(skfd, SIOCSIFFLAGS, &amp;ifr) &lt; 0) {
        perror("SIOCSIFFLAGS");
        return -1;
    }
    return (0);

} `
```

The userspace *ioctl()* system call is transformed to the *inet\_ioctl()* defined in *af\_inet.c*. For *ifconfig* (or any interface-type ioctls) *inet\_ioctl()* calls *devinet\_ioctl()* function.

```
460 int devinet_ioctl(unsigned int cmd, void *arg)
461 {
462         struct ifreq ifr;
463         struct sockaddr_in sin_orig;
464         struct sockaddr_in *sin = (struct sockaddr_in *)&ifr.ifr_addr;
465         struct in_device *in_dev;
466         struct in_ifaddr **ifap = NULL;
467         struct in_ifaddr *ifa = NULL;
468         struct net_device *dev;
469         char *colon;
470         int ret = 0;
471         int tryaddrmatch = 0;
472
473         /*
474          *      Fetch the caller's info block into kernel space
475          */
476
477         if (copy_from_user(&ifr, arg, sizeof(struct ifreq)))
478                 return -EFAULT;
479         ifr.ifr_name[IFNAMSIZ-1] = 0;
480
481         /* save original address for comparison */
482         memcpy(&sin_orig, sin, sizeof(*sin));
483
484         colon = strchr(ifr.ifr_name, ':');
485         if (colon)
486                 *colon = 0;
487
488 #ifdef CONFIG_KMOD
489         dev_load(ifr.ifr_name);
490 #endif
491
492         switch(cmd) {
493         case SIOCGIFADDR:       /* Get interface address */
494         case SIOCGIFBRDADDR:    /* Get the broadcast address */
495         case SIOCGIFDSTADDR:    /* Get the destination address */
496         case SIOCGIFNETMASK:    /* Get the netmask for the interface */
497                 /* Note that these ioctls will not sleep,
498                    so that we do not impose a lock.
499                    One day we will be forced to put shlock here (I mean SMP)
500                  */
501                 tryaddrmatch = (sin_orig.sin_family == AF_INET);
502                 memset(sin, 0, sizeof(*sin));
503                 sin->sin_family = AF_INET;
504                 break;
505
506         case SIOCSIFFLAGS:
507                 if (!capable(CAP_NET_ADMIN))
508                         return -EACCES;
509                 break;
510         case SIOCSIFADDR:       /* Set interface address (and family) */
511         case SIOCSIFBRDADDR:    /* Set the broadcast address */
512         case SIOCSIFDSTADDR:    /* Set the destination address */
513         case SIOCSIFNETMASK:    /* Set the netmask for the interface */
514                 if (!capable(CAP_NET_ADMIN))
515                         return -EACCES;
516                 if (sin->sin_family != AF_INET)
517                         return -EINVAL;
518                 break;
519         default:
520                 return -EINVAL;
521         }
522
523         dev_probe_lock();
524         rtnl_lock();
525
526         if ((dev = __dev_get_by_name(ifr.ifr_name)) == NULL) {
527                 ret = -ENODEV;
528                 goto done;
529         }
530
531         if (colon)
532                 *colon = ':';
533
534         if ((in_dev=__in_dev_get(dev)) != NULL) {
535                 if (tryaddrmatch) {
536                         /* Matthias Andree */
537                         /* compare label and address (4.4BSD style) */
538                         /* note: we only do this for a limited set of ioctls
539                            and only if the original address family was AF_INET.
540                            This is checked above. */
541                         for (ifap=&in_dev->ifa_list; (ifa=*ifap) != NULL; ifap=&ifa->ifa_next) {
542                                 if ((strcmp(ifr.ifr_name, ifa->ifa_label) == 0)
543                                     && (sin_orig.sin_addr.s_addr == ifa->ifa_address)) {
544                                         break; /* found */
545                                 }
546                         }
547                 }
548                 /* we didn't get a match, maybe the application is
549                    4.3BSD-style and passed in junk so we fall back to
550                    comparing just the label */
551                 if (ifa == NULL) {
552                         for (ifap=&in_dev->ifa_list; (ifa=*ifap) != NULL; ifap=&ifa->ifa_next)
553                                 if (strcmp(ifr.ifr_name, ifa->ifa_label) == 0)
554                                         break;
555                 }
556         }
557
558         if (ifa == NULL && cmd != SIOCSIFADDR && cmd != SIOCSIFFLAGS) {
559                 ret = -EADDRNOTAVAIL;
560                 goto done;
561         }
562
563         switch(cmd) {
564                 case SIOCGIFADDR:       /* Get interface address */
565                         sin->sin_addr.s_addr = ifa->ifa_local;
566                         goto rarok;
567
568                 case SIOCGIFBRDADDR:    /* Get the broadcast address */
569                         sin->sin_addr.s_addr = ifa->ifa_broadcast;
570                         goto rarok;
571
572                 case SIOCGIFDSTADDR:    /* Get the destination address */
573                         sin->sin_addr.s_addr = ifa->ifa_address;
574                         goto rarok;
575
576                 case SIOCGIFNETMASK:    /* Get the netmask for the interface */
577                         sin->sin_addr.s_addr = ifa->ifa_mask;
578                         goto rarok;
579
580                 case SIOCSIFFLAGS:
581                         if (colon) {
582                                 if (ifa == NULL) {
583                                         ret = -EADDRNOTAVAIL;
584                                         break;
585                                 }
586                                 if (!(ifr.ifr_flags&IFF_UP))
587                                         inet_del_ifa(in_dev, ifap, 1);
588                                 break;
589                         }
590                         ret = dev_change_flags(dev, ifr.ifr_flags);
591                         break;
592
593                 case SIOCSIFADDR:       /* Set interface address (and family) */
594                         if (inet_abc_len(sin->sin_addr.s_addr) < 0) {
595                                 ret = -EINVAL;
596                                 break;
597                         }
598
599                         if (!ifa) {
600                                 if ((ifa = inet_alloc_ifa()) == NULL) {
601                                         ret = -ENOBUFS;
602                                         break;
603                                 }
604                                 if (colon)
605                                         memcpy(ifa->ifa_label, ifr.ifr_name, IFNAMSIZ);
606                                 else
607                                         memcpy(ifa->ifa_label, dev->name, IFNAMSIZ);
608                         } else {
609                                 ret = 0;
610                                 if (ifa->ifa_local == sin->sin_addr.s_addr)
611                                         break;
612                                 inet_del_ifa(in_dev, ifap, 0);
613                                 ifa->ifa_broadcast = 0;
614                                 ifa->ifa_anycast = 0;
615                         }
616
617                         ifa->ifa_address =
618                         ifa->ifa_local = sin->sin_addr.s_addr;
619
620                         if (!(dev->flags&IFF_POINTOPOINT)) {
621                                 ifa->ifa_prefixlen = inet_abc_len(ifa->ifa_address);
622                                 ifa->ifa_mask = inet_make_mask(ifa->ifa_prefixlen);
623                                 if ((dev->flags&IFF_BROADCAST) && ifa->ifa_prefixlen < 31)
624                                         ifa->ifa_broadcast = ifa->ifa_address|~ifa->ifa_mask;
625                         } else {
626                                 ifa->ifa_prefixlen = 32;
627                                 ifa->ifa_mask = inet_make_mask(32);
628                         }
629                         ret = inet_set_ifa(dev, ifa);
630                         break;
631
632                 case SIOCSIFBRDADDR:    /* Set the broadcast address */
633                         if (ifa->ifa_broadcast != sin->sin_addr.s_addr) {
634                                 inet_del_ifa(in_dev, ifap, 0);
635                                 ifa->ifa_broadcast = sin->sin_addr.s_addr;
636                                 inet_insert_ifa(ifa);
637                         }
638                         break;
639
640                 case SIOCSIFDSTADDR:    /* Set the destination address */
641                         if (ifa->ifa_address != sin->sin_addr.s_addr) {
642                                 if (inet_abc_len(sin->sin_addr.s_addr) < 0) {
643                                         ret = -EINVAL;
644                                         break;
645                                 }
646                                 inet_del_ifa(in_dev, ifap, 0);
647                                 ifa->ifa_address = sin->sin_addr.s_addr;
648                                 inet_insert_ifa(ifa);
649                         }
650                         break;
651
652                 case SIOCSIFNETMASK:    /* Set the netmask for the interface */
653
654                         /*
655                          *      The mask we set must be legal.
656                          */
657                         if (bad_mask(sin->sin_addr.s_addr, 0)) {
658                                 ret = -EINVAL;
659                                 break;
660                         }
661
662                         if (ifa->ifa_mask != sin->sin_addr.s_addr) {
663                                 inet_del_ifa(in_dev, ifap, 0);
664                                 ifa->ifa_mask = sin->sin_addr.s_addr;
665                                 ifa->ifa_prefixlen =
666                                         inet_mask_len(ifa->ifa_mask);
667
668                                 /* See if current broadcast address matches
669                                  * with current netmask, then recalculate
670                                  * the broadcast address. Otherwise it's a
671                                  * funny address, so don't touch it since
672                                  * the user seems to know what (s)he's doing...
673                                  */
674                                 if ((dev->flags & IFF_BROADCAST) &&
675                                     (ifa->ifa_prefixlen < 31) &&
676                                     (ifa->ifa_broadcast ==
677                                      (ifa->ifa_local|~ifa->ifa_mask))) {
678                                         ifa->ifa_broadcast =
679                                                 (ifa->ifa_local |
680                                                  ~sin->sin_addr.s_addr);
681                                 }
682                                 inet_insert_ifa(ifa);
683                         }
684                         break;
685         }
686 done:
687         rtnl_unlock();
688         dev_probe_unlock();
689         return ret;
690
691 rarok:
692         rtnl_unlock();
693         dev_probe_unlock();
694         if (copy_to_user(arg, &ifr, sizeof(struct ifreq)))
695                 return -EFAULT;
696         return 0;
697 }
```

*devinet\_ioctl()* fetches the user space defined *ifreq* structure containing the name of our interface and the IP address to the kernel space. Based on the name of the interface (eth0, for e.g.), the device structure, *net\_device* (remember we created this in speedo\_found1() above?), is looked up [\*\_\_dev\_get\_by\_name()\* ]. The IP is set to this device by \*inet\_set\_ifa()\*.

## Shared Memory Communication Architecture

After initialization, 82559 is ready for its normal operation. As a Fast Ethernet Controller, its normal operation is to transmit and receive data packets. As a PCI bus master device, 82559 works independently, without CPU intervention. The CPU provides the 82559 with action commands and pointers to the data buffers that reside in host main memory. The 82559 independently manages these structures and initiates burst memory cycles to transfer data to and from main memory.

The CPU controls and examines 82559 via its control and status structures. Some of these control and status structures reside within the 82559 and some reside in system memory. For transfer of data to/from the CPU, the 82559 establishes a shared memory communication with the host CPU. This shared memory is divided into three parts:

- The Control/Status Registers (CSR)
- The Command Block List (CBL) or just Command List (CL)
- The Receive Frame Area (RFA).

The CSR resides on-chip and can be accessed by either I/O or memory cycles (after the PCI BIOS has mapped this region to a region accessible by the CPU. See the section PCI Kernel Initialization), while the CBL and RFA reside in system (host) memory.

Command Block List (CBL) is a linked list of commands to be executed by 82559. Receive Frame Area (RFA) is a linked list of data structures that holds the received packets (frames).

![](/images/external/i.imgur.com/N8dZtfE.jpg)

### Controlling 82559 through CSR

The 82559 has seven Control/Status registers which make up the CSR space.

![](/images/external/i.imgur.com/rmgOuzr.jpg)

The first 8 bytes of the CSR is called the System Control Block (SCB). The SCB serves as a central communication point for exchanging control and status information between the host CPU and the 82559.

The CPU instructs the 82559 to Activate, Suspend, Resume or Idle the Command Unit (CU) or Receive Unit (RU) by placing the appropriate control command in the CU or RU control field of SCB. Activating the CU causes the 82559 to begin transmitting packets. When transmission is completed, the 82559 updates the SCB with the CU status then interrupts the CPU, if configured to do so. Activating the RU causes the 82559 to go into the READY state for frame reception. When a frame is received the RU updates the SCB with the RU status and interrupts the CPU.

## Command Block List (CBL) and Transmitted Frame

Transmit or configure commands issued by CPU are wrapped inside what are called Command Blocks (CB). These command blocks are chained together to form the CBL.

![](/images/external/i.imgur.com/nqCnsvZ.jpg)

Action commands are categorized into two types:

- Non-Tx commands: This category includes commands such as NOP, Configure, IA Setup, Multicast Setup, Dump and Diagnose.
- Tx command: This command causes the 82559 to transmit a frame. A transmit command block contains (in the parameter field) the destination address, length of the transmitted frame and a pointer to buffer area in memory containing the data portion of the frame. The data field is contained in a memory data structure consisting of a buffer descriptor (BD) and a data buffer, or a linked list of buffer descriptors and buffers (as shown in figure below).

![](/images/external/i.imgur.com/dc7Ps7T.jpg)

When eepro100 is ready to transmit a packet, it must create this Tx command block and send it to 82559. This Tx Command block is a structure called TxFD (Transmit Frame Descriptor).

```
406 #define CONFIG_DATA_SIZE 22
407 struct TxFD {                                   /* Transmit frame descriptor set. */
408         s32 status;
409         u32 link;                                       /* void * */
410         u32 tx_desc_addr;                       /* Always points to the tx_buf_addr element. */
411         s32 count;                                      /* # of TBD (=1), Tx start thresh., etc. */
412         /* This constitutes two "TBD" entries -- we only use one. */
413 #define TX_DESCR_BUF_OFFSET 16
414         u32 tx_buf_addr0;                       /* void *, frame to be transmitted.  */
415         s32 tx_buf_size0;                       /* Length of Tx frame. */
416         u32 tx_buf_addr1;                       /* void *, frame to be transmitted.  */
417         s32 tx_buf_size1;                       /* Length of Tx frame. */
418         /* the structure must have space for at least CONFIG_DATA_SIZE starting
419          * from tx_desc_addr field */
420 };
```

This TxFD can hold one TxCB and two Tx Buffer Descriptors (TxBD). During eepro100 initialization (*speedo\_found1()*), a fixed number of these TxFD's are created and linked together into a ring (*tx\_ring\_space*). When new data is available for transmission, one of the TxFD is fetched from the ring and sent to 82559 for transmission.

The status field of TxFD is a bit array and can contain any of:

```
342 /* Commands that can be put in a command list entry. */
343 enum commands {
344         CmdNOp = 0, CmdIASetup = 0x10000, CmdConfigure = 0x20000,
345         CmdMulticastList = 0x30000, CmdTx = 0x40000, CmdTDR = 0x50000,
346         CmdDump = 0x60000, CmdDiagnose = 0x70000,
347         CmdSuspend = 0x40000000,        /* Suspend after completion. */
348         CmdIntr = 0x20000000,           /* Interrupt after completion. */
349         CmdTxFlex = 0x00080000,         /* Use "Flexible mode" for CmdTx command. */
350 };
```

### Receive Frame Area

To reduce CPU overhead, the 82559 is designed to receive frames without CPU supervision. The host CPU first sets aside an adequate receive buffer space and then enables the 82559 Receive Unit (This is done in *speedo\_init\_rx\_ring* when the device is opened: *speedo\_open*). Once enabled, the RU watches for arriving frames and automatically stores them in the Receive Frame Area (RFA).

The RFA contains Receive Frame Descriptors, Receive Buffer Descriptors, and Receive Buffers (see figure below).

![](/images/external/i.imgur.com/teVQ9ZJ.jpg)

The individual Receive Frame Descriptors make up a Receive Descriptor List (RDL) used by the 82559 to store the destination and source addresses, the length field, and the status of each frame received.

![](/images/external/i.imgur.com/GQyuQtv.jpg)

eepro100 representation of the Receive Frame Descriptor (RxFD):

```
390 /* The Speedo3 Rx and Tx buffer descriptors. */
391 struct RxFD {                                   /* Receive frame descriptor. */
392         volatile s32 status;
393         u32 link;                                       /* struct RxFD * */
394         u32 rx_buf_addr;                        /* void * */
395         u32 count;
396 } RxFD_ALIGNMENT;
397
398 /* Selected elements of the Tx/RxFD.status word. */
399 enum RxFD_bits {
400         RxComplete=0x8000, RxOK=0x2000,
401         RxErrCRC=0x0800, RxErrAlign=0x0400, RxErrTooBig=0x0200, RxErrSymbol=0x0010,
402         RxEth2Type=0x0020, RxNoMatch=0x0004, RxNoIAMatch=0x0002,
403         TxUnderrun=0x1000,  StatusComplete=0x8000,
404 };
```

## Data Transmission

An application calls *write(socket, data, length)* system call to write to an open socket. In the kernel, *inet\_sendmsg()* is executed with a pointer to the sock structure. *inet\_sendmsg()* calls the send operation of the corresponding transport protocol which for TCP is *tcp\_sendmsg()*. *tcp\_sendmsg()* copies the data to be transmitted from the user space to the socket and starts the transmit process by calling *tcp\_send\_skb()* and subsequently *tcp\_transmitt\_skb()*. *tcp\_transmitt\_skb()* adds the TCP Header to the packet, calculate the TCP checksum and call the *ip\_queue\_xmit()*. Determining the ip route and construction of the IP header happens in *ip\_queue\_xmit()*. Finally the MAC address is copied to the packet and *dev\_queue\_xmit()* is called to send the packet to the ethernet device.

*dev\_queue\_xmit()* points to a driver specific function. In case of eepro100, this function is *speedo\_start\_xmit()* (remember we set this in *speedo\_found1()*?).

```
1435 static int
1436 speedo_start_xmit(struct sk_buff *skb, struct net_device *dev)
1437 {
1438         struct speedo_private *sp = (struct speedo_private *)dev->priv;
1439         long ioaddr = dev->base_addr;
1440         int entry;
1441
1442         /* Prevent interrupts from changing the Tx ring from underneath us. */
1443         unsigned long flags;
1444
1445         spin_lock_irqsave(&sp->lock, flags);
1446
1447         /* Check if there are enough space. */
1448         if ((int)(sp->cur_tx - sp->dirty_tx) >= TX_QUEUE_LIMIT) {
1449                 printk(KERN_ERR "%s: incorrect tbusy state, fixed.\n", dev->name);
1450                 netif_stop_queue(dev);
1451                 sp->tx_full = 1;
1452                 spin_unlock_irqrestore(&sp->lock, flags);
1453                 return 1;
1454         }
1455
1456         /* Calculate the Tx descriptor entry. */
1457         entry = sp->cur_tx++ % TX_RING_SIZE;
1458
1459         sp->tx_skbuff[entry] = skb;
1460         sp->tx_ring[entry].status =
1461                 cpu_to_le32(CmdSuspend | CmdTx | CmdTxFlex);
1462         if (!(entry & ((TX_RING_SIZE>>2)-1)))
1463                 sp->tx_ring[entry].status |= cpu_to_le32(CmdIntr);
1464         sp->tx_ring[entry].link =
1465                 cpu_to_le32(TX_RING_ELEM_DMA(sp, sp->cur_tx % TX_RING_SIZE));
1466         sp->tx_ring[entry].tx_desc_addr =
1467                 cpu_to_le32(TX_RING_ELEM_DMA(sp, entry) + TX_DESCR_BUF_OFFSET);
1468         /* The data region is always in one buffer descriptor. */
1469         sp->tx_ring[entry].count = cpu_to_le32(sp->tx_threshold);
1470         sp->tx_ring[entry].tx_buf_addr0 =
1471                 cpu_to_le32(pci_map_single(sp->pdev, skb->data,
1472                                            skb->len, PCI_DMA_TODEVICE));
1473         sp->tx_ring[entry].tx_buf_size0 = cpu_to_le32(skb->len);
1474
1475         /* workaround for hardware bug on 10 mbit half duplex */
1476
1477         if ((sp->partner == 0) && (sp->chip_id == 1)) {
1478                 wait_for_cmd_done(dev);
1479                 outb(0 , ioaddr + SCBCmd);
1480                 udelay(1);
1481         }
1482
1483         /* Trigger the command unit resume. */
1484         wait_for_cmd_done(dev);
1485         clear_suspend(sp->last_cmd);
1486         /* We want the time window between clearing suspend flag on the previous
1487            command and resuming CU to be as small as possible.
1488            Interrupts in between are very undesired.  --SAW */
1489         outb(CUResume, ioaddr + SCBCmd);
1490         sp->last_cmd = (struct descriptor *)&sp->tx_ring[entry];
1491
1492         /* Leave room for set_rx_mode(). If there is no more space than reserved
1493            for multicast filter mark the ring as full. */
1494         if ((int)(sp->cur_tx - sp->dirty_tx) >= TX_QUEUE_LIMIT) {
1495                 netif_stop_queue(dev);
1496                 sp->tx_full = 1;
1497         }
1498
1499         spin_unlock_irqrestore(&sp->lock, flags);
1500
1501         dev->trans_start = jiffies;
1502
1503         return 0;
1504 }
```

*speedo\_start\_xmit()* inserts any data received from the kernel (skb) into the Tx ring. If there are no open slots in the Tx ring, *netif\_stop\_queue()* is called to request the kernel to stop sending more packets from the upper layers and flag the Tx ring as full. The new skb (data) to be transmitted is inserted as the data portion of a TxFD at *tx\_buf\_addr0* (See TxFD above).

The TxFD status of this entry is set to *CmdSuspend* (suspend after completion), *CmdTx* and *CmdFlex* (flexible transmission mode). The last command inserted into the Tx ring has the *CmdSuspend* bit set so that the CU is suspended immediately after the last command is executed. This way we prevent any erroneous data from being transmitted. We have to clear the *CmdSuspend* from the previous command already in the Tx ring before doing this. If the Tx ring is more than half full, we also set *CmdIntr* (interrupt after completion). The causes the chip to generates an interrupt after executing this command. When an interrupt is received after transmit completes, the interrupt handler calls *speedo\_tx\_buffer\_gc()* to clean up completed and erroneous skb from the Tx ring.

Finally, we activate the CU to transmit this new packet by issuing *CmdResume* to SCB.

### Generating the Ethernet Frame

The final ethernet frame sent over the wire is:

![](/images/external/i.imgur.com/c3jcUWq.jpg)

82559 automatically generates the preamble (alternating 1s and 0s) and start frame delimiter, fetches the destination address and length field from the Transmit command, inserts its unique MAC address (that it fetched from the external Flash/EEPROM) as the source address, fetches the data field specified by the Transmit command, and computes and appends the CRC to the end of the frame.

This final frame is then handed over to the PHY layer for transmission over the wire.

## Bits to Waves

82559 has an internal 82555 Physical Layer Interface (PHY). It is responsible for connecting the 82559 to the actual physical wire over which the data will be carried. PHY converts the incoming digital data to analog signals during transmission and analog signals to digital data during reception.

### Signal Transmission

To achieve a high transfer rate (upto 125Mbps), two tasks must be performed to the data before it is transmitted over the wire:

- scrambling/descrambling
- encoding/decoding

![](/images/external/i.imgur.com/CL3O60M.jpg)

### Scrambling/Descrambling

All data transmitted and received over wire are synchronized with a clock. To keep the receiver in sync with the transmitter, the clock signals have to be embedded in the signal transmitted over the wire itself. The robustness of this digitally transmitted synchronization signal often depends on the statistical nature of the data being transmitted. For example, long strings of 0â€™s and 1â€™s can cause loss of the synchronization since the receiver clock is derived from the received data. Therefore, data must contain adequate transitions to assure that the timing recovery circuit at the receiver will stay in synchronization. Scrambling (randomizing) the data over a period of time spreads these patterns.

### Encoding/Decoding

There are different ways to represent the digital 1 & 0 over the wire. The most widely used is Non-Return to Zero (NRZI) format. NRZI, is a two level unipolar code (0 and V) representing a "one" by a transition between two levels and a "zero" is represented by no transition as shown in the figure below. Another format is MLT-3. MLT-3 is a three level eenting a "one" by a transition between two levels and "zero" as no transition as shown in figure below. MLT-3 has the advantage that the maximum fundamental frequency of MLT-3 is one-half that of NRZI. With the MLT-3 coding scheme, 90% of the spectral energy is below 40MHz versus 70MHz for NRZI. Thus we can achieves the same data rate as NRZI, but do not require a wideband transmission medium. The work of the encoder/decoder is to convert between NRZI and MLT-3.

![](/images/external/i.imgur.com/nd4kTFs.jpg)

Finally, the MLT-3 encoded data is transmitted over the wire. It is important to isolate the the PHY from the CAT-5 Ethernet cable for load balancing and also feedback. This is done by using specialized Ethernet magnetics with each side of the transformer referenced to the appropriate ground.

{% cimg http://interviewquestions.pupilgarage.com/images/EC%20Images/EC\_Fig03.gif PHY to Magnetics interface %}

### Signal Reception

Once the PHY detects signals on the receive side, it decodes and descrambles it to reconstruct the data transmitted by the receiver.

### Receiving Frames

To reduce CPU overhead, the 82559 is designed to receive frames without CPU supervision. The eepro100 had already setup the address of the receive buffer ring in the SCB as part of initialization. Once the 82559 receive unit (RU) is enabled, the RU watches for arriving frames and automatically stores them in the Rx ring / Receive Frame Area (RFA). The RFA contains Receive Frame Descriptors, Receive Buffer Descriptors, and Data Buffers (see Figure 2). The individual Receive Frame Descriptors make up a Receive Descriptor List (RDL) used by the 82559 to store the destination and source addresses, the length field, and the status of each frame received.

![](/images/external/i.imgur.com/8FzzgKZ.jpg)

82559 checks each passing frame for an address match. The 82559 will recognize its own unique address, one or more multicast addresses, or the broadcast address. If a match is found, 82559 stores the destination address, source addresses and the length field in the next available Receive Frame Descriptor (RFD). It then begins filling the next available Data Buffer on the Receive Buffer Descriptor (RBD). As one Data Buffer is filled, the 82559 automatically fetches the next Data Buffer & RBD until the entire frame is received.

Once the entire frame is received without error, a frame received interrupt status bit is posted in the SCB and an interrupt is sent to the CPU.

The interrupt handler (*speedo\_interrupt()*) checks if the receive interrupt bit is set in SCB and calls *speedo\_rx()* to handle the received packet.

```
1756 static int
1757 speedo_rx(struct net_device *dev)
1758 {
1759         struct speedo_private *sp = (struct speedo_private *)dev->priv;
1760         int entry = sp->cur_rx % RX_RING_SIZE;
1761         int rx_work_limit = sp->dirty_rx + RX_RING_SIZE - sp->cur_rx;
1762         int alloc_ok = 1;
1763         int npkts = 0;
1764
1765         if (netif_msg_intr(sp))
1766                 printk(KERN_DEBUG " In speedo_rx().\n");
1767         /* If we own the next entry, it's a new packet. Send it up. */
1768         while (sp->rx_ringp[entry] != NULL) {
1769                 int status;
1770                 int pkt_len;
1771
1772                 pci_dma_sync_single(sp->pdev, sp->rx_ring_dma[entry],
1773                         sizeof(struct RxFD), PCI_DMA_FROMDEVICE);
1774                 status = le32_to_cpu(sp->rx_ringp[entry]->status);
1775                 pkt_len = le32_to_cpu(sp->rx_ringp[entry]->count) & 0x3fff;
1776
1777                 if (!(status & RxComplete))
1778                         break;
1779
1780                 if (--rx_work_limit < 0)
1781                         break;
1782
1783                 /* Check for a rare out-of-memory case: the current buffer is
1784                    the last buffer allocated in the RX ring.  --SAW */
1785                 if (sp->last_rxf == sp->rx_ringp[entry]) {
1786                         /* Postpone the packet.  It'll be reaped at an interrupt when this
1787                            packet is no longer the last packet in the ring. */
1788                         if (netif_msg_rx_err(sp))
1789                                 printk(KERN_DEBUG "%s: RX packet postponed!\n",
1790                                            dev->name);
1791                         sp->rx_ring_state |= RrPostponed;
1792                         break;
1793                 }
1794
1795                 if (netif_msg_rx_status(sp))
1796                         printk(KERN_DEBUG "  speedo_rx() status %8.8x len %d.\n", status,
1797                                    pkt_len);
1798                 if ((status & (RxErrTooBig|RxOK|0x0f90)) != RxOK) {
1799                         if (status & RxErrTooBig)
1800                                 printk(KERN_ERR "%s: Ethernet frame overran the Rx buffer, "
1801                                            "status %8.8x!\n", dev->name, status);
1802                         else if (! (status & RxOK)) {
1803                                 /* There was a fatal error.  This *should* be impossible. */
1804                                 sp->stats.rx_errors++;
1805                                 printk(KERN_ERR "%s: Anomalous event in speedo_rx(), "
1806                                            "status %8.8x.\n",
1807                                            dev->name, status);
1808                         }
1809                 } else {
1810                         struct sk_buff *skb;
1811
1812                         /* Check if the packet is long enough to just accept without
1813                            copying to a properly sized skbuff. */
1814                         if (pkt_len < rx_copybreak
1815                                 && (skb = dev_alloc_skb(pkt_len + 2)) != 0) {
1816                                 skb->dev = dev;
1817                                 skb_reserve(skb, 2);    /* Align IP on 16 byte boundaries */
1818                                 /* 'skb_put()' points to the start of sk_buff data area. */
1819                                 pci_dma_sync_single(sp->pdev, sp->rx_ring_dma[entry],
1820                                         sizeof(struct RxFD) + pkt_len, PCI_DMA_FROMDEVICE);
1821
1822 #if 1 || USE_IP_CSUM
1823                                 /* Packet is in one chunk -- we can copy + cksum. */
1824                                 eth_copy_and_sum(skb, sp->rx_skbuff[entry]->tail, pkt_len, 0);
1825                                 skb_put(skb, pkt_len);
1826 #else
1827                                 memcpy(skb_put(skb, pkt_len), sp->rx_skbuff[entry]->tail,
1828                                            pkt_len);
1829 #endif
1830                                 npkts++;
1831                         } else {
1832                                 /* Pass up the already-filled skbuff. */
1833                                 skb = sp->rx_skbuff[entry];
1834                                 if (skb == NULL) {
1835                                         printk(KERN_ERR "%s: Inconsistent Rx descriptor chain.\n",
1836                                                    dev->name);
1837                                         break;
1838                                 }
1839                                 sp->rx_skbuff[entry] = NULL;
1840                                 skb_put(skb, pkt_len);
1841                                 npkts++;
1842                                 sp->rx_ringp[entry] = NULL;
1843                                 pci_unmap_single(sp->pdev, sp->rx_ring_dma[entry],
1844                                                 PKT_BUF_SZ + sizeof(struct RxFD), PCI_DMA_FROMDEVICE);
1845                         }
1846                         skb->protocol = eth_type_trans(skb, dev);
1847                         netif_rx(skb);
1848                         sp->stats.rx_packets++;
1849                         sp->stats.rx_bytes += pkt_len;
1850                 }
1851                 entry = (++sp->cur_rx) % RX_RING_SIZE;
1852                 sp->rx_ring_state &= ~RrPostponed;
1853                 /* Refill the recently taken buffers.
1854                    Do it one-by-one to handle traffic bursts better. */
1855                 if (alloc_ok && speedo_refill_rx_buf(dev, 0) == -1)
1856                         alloc_ok = 0;
1857         }
1858
1859         /* Try hard to refill the recently taken buffers. */
1860         speedo_refill_rx_buffers(dev, 1);
1861
1862         if (npkts)
1863                 sp->last_rx_time = jiffies;
1864
1865         return 0;
1866 }
```

The receive is a very simple process as most of the work is handled by the 82559 chip. 82559 while storing the packet on the Rx ring has already determined the size of the packet, it stores this along with other relevent information like the receive status in the Rx buffer. *speedo\_rx()* checks the status to make sure there were no errors in receiving the frame.

The driver receives packets into full-sized buffers - 1560 bytes. When a packet comes in, the driver needs to make a decision. Does it use the whole 1560 bytes for this packet, or does it allocate a smaller buffer on-the-fly and copy the data into it? If the size of the frame received is smaller than the *rx\_copybreak*, then a new buffer is allocated and the data is copied into it. If the packet is larger than *rx\_copybreak*, we remove the received skbuff (leaving a hole in the Rx ring) and pass this buffer to the higher applications. We later call *speedo\_refill\_rx\_buffers()* to refill the hole in the Rx ring.

The type of protocol of this packet is determined by calling *eth\_type\_trans()*. The packet is then queued for the upper layers to process using the *netif\_rx()*. Finally we refill the buffer we just took out of the Rx ring.

### References

- [Intel 82555 10/100 Mbps LAN Physical Layer Interface](http://pcmcia-cs.sourceforge.net/specs/i82555.pdf "Intel 82555")
- [Intel 82559 Fast Ethernet PCI Controller Data Sheet](http://www.intel.com/content/www/us/en/ethernet-controllers/82559er-fast-ethernet-pci-datasheet.html "Intel 82559 Fast Ethernet Controller Datasheet")
- [Intel 8255X 10/100 Mbps Ethernet Controller Family Open Source Manual](http://www.intel.com/content/www/us/en/ethernet-controllers/8255x-10-100-mbps-ethernet-controller-software-dev-manual.html "Intel 8255X 10/100 Mbps Ethernet Controller Family Open Source Manual ")
- [eepro100.c Linux Device Driver](http://lxr.linux.no/#linux-bk+v2.6.11.5/drivers/net/eepro100.c "eepro100.c Linux Device Driver")
