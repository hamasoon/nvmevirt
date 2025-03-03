// SPDX-License-Identifier: GPL-2.0-only

#ifndef _NVMEVIRT_SSD_H
#define _NVMEVIRT_SSD_H

#include <linux/types.h>
#include "pqueue/pqueue.h"
#include "ssd_config.h"
#include "channel_model.h"
#include "conv_ftl.h"

/*
    Default malloc size (when sector size is 512B)
    Channel = 40 * 8 = 320
    LUN     = 40 * 8 = 320
    Plane   = 16 * 1 = 16
    Block   = 32 * 256 = 8192
    Page    = 16 * 256 = 4096
    Sector  = 4 * 8 = 32

    Line    = 40 * 256 = 10240
    maptbl  = 8 * 4194304 = 33554432
    rmap    = 8 * 4194304 = 33554432
*/

#define INVALID_PPA (~(0ULL))
#define INVALID_LPN (~(0ULL))
#define UNMAPPED_PPA (~(0ULL))
#define GET_FTL_IDX(lpn) (lpn / (FLASH_PAGE_SIZE / LOGICAL_PAGE_SIZE) % SSD_PARTITIONS)
#define LOCAL_LPN(lpn) ((lpn / ((FLASH_PAGE_SIZE / LOGICAL_PAGE_SIZE) * SSD_PARTITIONS))\
		* (FLASH_PAGE_SIZE / LOGICAL_PAGE_SIZE) + (lpn % (FLASH_PAGE_SIZE / LOGICAL_PAGE_SIZE)))

enum {
	NAND_READ = 0,
	NAND_WRITE = 1,
	NAND_ERASE = 2,
	NAND_NOP = 3,
};

enum {
	USER_IO = 0,
	GC_IO = 1,
};

enum {
	SEC_FREE = 0,
	SEC_INVALID = 1,
	SEC_VALID = 2,

	PG_FREE = 0,
	PG_INVALID = 1,
	PG_VALID = 2
};

enum {
	VALID = 0,
	RMW_TARGET = 1,
	FLUSHING = 2,
};

/* Cell type */
enum { CELL_TYPE_LSB, CELL_TYPE_MSB, CELL_TYPE_CSB, MAX_CELL_TYPES };

#define TOTAL_PPA_BITS (64)
#define BLK_BITS (16)
#define PAGE_BITS (16)
#define PL_BITS (8)
#define LUN_BITS (8)
#define CH_BITS (8)
#define RSB_BITS (TOTAL_PPA_BITS - (BLK_BITS + PAGE_BITS + PL_BITS + LUN_BITS + CH_BITS))

/* describe a physical page addr */
struct ppa {
	union {
		struct {
			uint64_t pg : PAGE_BITS; // pg == 4KB
			uint64_t blk : BLK_BITS;
			uint64_t pl : PL_BITS;
			uint64_t lun : LUN_BITS;
			uint64_t ch : CH_BITS;
			uint64_t rsv : RSB_BITS;
		} g;

		struct {
			uint64_t : PAGE_BITS;
			uint64_t blk_in_ssd : BLK_BITS + PL_BITS + LUN_BITS + CH_BITS;
			uint64_t rsv : RSB_BITS;
		} h;

		uint64_t ppa;
	};
};

typedef int nand_sec_status_t;

struct nand_page {
	nand_sec_status_t *sec;
	int nsecs;
	int status;
};

struct nand_block {
	struct nand_page *pg;
	int npgs;
	int ipc; /* invalid page count */
	int vpc; /* valid page count */
	int erase_cnt;
	int wp; /* current write pointer */
};

struct nand_plane {
	struct nand_block *blk;
	uint64_t next_pln_avail_time;
	int nblks;
};

struct nand_lun {
	struct nand_plane *pl;
	int npls;
	uint64_t next_lun_avail_time;
	bool busy;
	uint64_t gc_endtime;
};

struct ssd_channel {
	struct nand_lun *lun;
	int nluns;
	uint64_t gc_endtime;
	struct channel_model *perf_model;
};

struct ssd_pcie {
	struct channel_model *perf_model;
};

struct nand_cmd {
	int type;
	int cmd;
	uint64_t xfer_size; // byte
	uint64_t stime; /* Coperd: request arrival time */
	bool interleave_pci_dma;
	struct ppa *ppa;
};

/*
size: size of buffer
ppg_per_buf: number of blocks
block_size: size of block. same as page size
flush_threshold: threshold for flushing buffer(currently half of ppg_per_buf)
free_ppgs: list of free blocks
used_ppgs: list of used blocks
*/
struct buffer {
	spinlock_t lock;
	size_t size;
	size_t ppg_per_buf;
	size_t pg_per_ppg;
	size_t sec_per_pg;
	size_t ppg_size;
	size_t pg_size;
	// size_t free_pgs_cnt;
	size_t flush_threshold;
	size_t buffer_high_watermark;
	size_t buffer_low_watermark;
	size_t free_ppgs_cnt;
	size_t used_ppgs_cnt;
	size_t flushing_ppgs_cnt;
	struct list_head free_ppgs;
	struct list_head used_ppgs;
};

/*
lpn: logical page number
valid: whether the block is valid. if false, the block is currently begin written to NAND
sectors: represent the sectors of the page
list: list head for buffer
*/
struct buffer_ppg {
	int status;
	int ftl_idx;	
	int pg_idx;
	size_t full_pages_cnt;
	uint64_t access_time;
	uint64_t complete_time;
	struct buffer_page *pages;
    struct list_head list;
};

struct buffer_page {
	uint64_t lpn;
	size_t free_secs;
	bool *sectors;
	struct buffer_ppg *ppg;
};

/*
pg (page): Mapping unit (4KB)
flashpg (flash page) : Nand sensing unit , tR
oneshotpg (oneshot page) : Nand program unit, tPROG, (eg. flashpg * 3 (TLC))
blk (block): Nand erase unit
lun (die) : Nand operation unit
ch (channel) : Nand <-> SSD controller data transfer unit
*/
struct ssdparams {
	int secsz; /* sector size in bytes */
	int secs_per_pg; /* # of sectors per page */
	int pgsz; /* mapping unit size in bytes*/
	int pgs_per_flashpg; /* # of pgs per flash page */
	int flashpgs_per_blk; /* # of flash pages per block */
	int pgs_per_oneshotpg; /* # of pgs per oneshot page */
	int oneshotpgs_per_blk; /* # of oneshot pages per block */
	int pgs_per_blk; /* # of pages per block */
	int blks_per_pl; /* # of blocks per plane */
	int pls_per_lun; /* # of planes per LUN (Die) */
	int luns_per_ch; /* # of LUNs per channel */
	int nchs; /* # of channels in the SSD */
	int cell_mode;

	/* Unit size of NVMe write command
       Transfer size should be multiple of it */
	int write_unit_size;
	bool write_early_completion;

	int pg_4kb_rd_lat
		[MAX_CELL_TYPES]; /* NAND page 4KB read latency in nanoseconds. sensing time (half tR) */
	int pg_rd_lat[MAX_CELL_TYPES]; /* NAND page read latency in nanoseconds. sensing time (tR) */
	int pg_wr_lat; /* NAND page program latency in nanoseconds. pgm time (tPROG)*/
	int blk_er_lat; /* NAND block erase latency in nanoseconds. erase time (tERASE) */
	int max_ch_xfer_size;

	int fw_4kb_rd_lat; /* Firmware overhead of 4KB read of read in nanoseconds */
	int fw_rd_lat; /* Firmware overhead of read of read in nanoseconds */
	int fw_wbuf_lat0; /* Firmware overhead0 of write buffer in nanoseconds */
	int fw_wbuf_lat1; /* Firmware overhead1 of write buffer in nanoseconds */
	int fw_ch_xfer_lat; /* Firmware overhead of nand channel data transfer(4KB) in nanoseconds */

	uint64_t ch_bandwidth; /*NAND CH Maximum bandwidth in MiB/s*/
	uint64_t pcie_bandwidth; /*PCIE Maximum bandwidth in MiB/s*/

	/* below are all calculated values */
	unsigned long secs_per_blk; /* # of sectors per block */
	unsigned long secs_per_pl; /* # of sectors per plane */
	unsigned long secs_per_lun; /* # of sectors per LUN */
	unsigned long secs_per_ch; /* # of sectors per channel */
	unsigned long tt_secs; /* # of sectors in the SSD */

	unsigned long pgs_per_pl; /* # of pages per plane */
	unsigned long pgs_per_lun; /* # of pages per LUN (Die) */
	unsigned long pgs_per_ch; /* # of pages per channel */
	unsigned long tt_pgs; /* total # of pages in the SSD */

	unsigned long blks_per_lun; /* # of blocks per LUN */
	unsigned long blks_per_ch; /* # of blocks per channel */
	unsigned long tt_blks; /* total # of blocks in the SSD */

	unsigned long secs_per_line;
	unsigned long pgs_per_line;
	unsigned long blks_per_line;
	unsigned long tt_lines;

	unsigned long pls_per_ch; /* # of planes per channel */
	unsigned long tt_pls; /* total # of planes in the SSD */

	unsigned long tt_luns; /* total # of LUNs in the SSD */

	unsigned long long write_buffer_size;
};

struct ssd {
	struct ssdparams sp;
	struct ssd_channel *ch;
	struct ssd_pcie *pcie;
	struct buffer *write_buffer;
	unsigned int cpu_nr_dispatcher;
};

static inline struct ssd_channel *get_ch(struct ssd *ssd, struct ppa *ppa)
{
	return &(ssd->ch[ppa->g.ch]);
}

static inline struct nand_lun *get_lun(struct ssd *ssd, struct ppa *ppa)
{
	struct ssd_channel *ch = get_ch(ssd, ppa);
	return &(ch->lun[ppa->g.lun]);
}

static inline struct nand_plane *get_pl(struct ssd *ssd, struct ppa *ppa)
{
	struct nand_lun *lun = get_lun(ssd, ppa);
	return &(lun->pl[ppa->g.pl]);
}

static inline struct nand_block *get_blk(struct ssd *ssd, struct ppa *ppa)
{
	struct nand_plane *pl = get_pl(ssd, ppa);
	return &(pl->blk[ppa->g.blk]);
}

static inline struct nand_page *get_pg(struct ssd *ssd, struct ppa *ppa)
{
	struct nand_block *blk = get_blk(ssd, ppa);
	return &(blk->pg[ppa->g.pg]);
}

static inline uint32_t get_cell(struct ssd *ssd, struct ppa *ppa)
{
	struct ssdparams *spp = &ssd->sp;
	return (ppa->g.pg / spp->pgs_per_flashpg) % (spp->cell_mode);
}

void ssd_init_params(struct ssdparams *spp, uint64_t capacity, uint32_t nparts);
void ssd_init(struct ssd *ssd, struct ssdparams *spp, uint32_t cpu_nr_dispatcher);
void ssd_remove(struct ssd *ssd);

uint64_t ssd_advance_nand(struct ssd *ssd, struct nand_cmd *ncmd);
uint64_t ssd_advance_pcie(struct ssd *ssd, uint64_t request_time, uint64_t length);
uint64_t ssd_advance_write_buffer(struct ssd *ssd, uint64_t request_time, uint64_t length);
uint64_t ssd_next_idle_time(struct ssd *ssd);

void buffer_init(struct buffer *buf, size_t size, struct ssdparams *spp);
bool buffer_allocatable_check(struct buffer *buf, uint64_t start_lpn, uint64_t end_lpn, uint64_t start_offset, uint64_t size);
void buffer_allocate(struct buffer *buf, uint64_t start_lpn, uint64_t end_lpn, uint64_t start_offset, uint64_t size);
bool buffer_release(struct buffer *buf, uint64_t complete_time);
void buffer_refill(struct buffer *buf);
struct buffer_page *buffer_search(struct buffer *buf, uint64_t lpn);

void adjust_ftl_latency(int target, int lat);
#endif
