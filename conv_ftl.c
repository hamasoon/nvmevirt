// SPDX-License-Identifier: GPL-2.0-only
#include <linux/ktime.h>
#include <linux/sched/clock.h>
#include <linux/vmalloc.h>

#include "nvmev.h"
#include "conv_ftl.h"
#define ROUND_DOWN(x, y) ((x) & ~((y)-1))
#define ROUND_UP(x, y) ((((x) + (y) - 1) / (y)) * (y))
#define sq_entry(entry_id) sq->sq[SQ_ENTRY_TO_PAGE_NUM(entry_id)][SQ_ENTRY_TO_PAGE_OFFSET(entry_id)]
#define cq_entry(entry_id) cq->cq[CQ_ENTRY_TO_PAGE_NUM(entry_id)][CQ_ENTRY_TO_PAGE_OFFSET(entry_id)]

static uint64_t time = 0;
static bool full_waiting = false;

// check number of free blocks in buffer less than threshold
// currently, threshold is half of the total blocks
static inline bool check_flush_buffer(struct buffer *buf)
{
#if (FLUSH_TIMING_POLICY == IMMEDIATE)
	return false;
#elif (FLUSH_TIMING_POLICY == FULL)
	return false;
#elif (FLUSH_TIMING_POLICY == WATERMARK_NAIVE || FLUSH_TIMING_POLICY == WATERMARK_DOUBLE || FLUSH_TIMING_POLICY == WATERMARK_ONDEMAND)
	size_t used_ppgs_cnt = 0;
	size_t full_ppgs_cnt = 0;
	struct buffer_ppg *block;
	list_for_each_entry(block, &buf->used_ppgs, list) {
		if (block->status == VALID) {
			used_ppgs_cnt++;
			if (block->pg_idx >= buf->pg_per_ppg) {
				full_ppgs_cnt++;
			}
		}
	}
#endif
}

static inline bool check_flush_buffer_allocate_fail(struct buffer *buf)
{
#if (FLUSH_TIMING_POLICY == IMMEDIATE)
	return false;
#elif (FLUSH_TIMING_POLICY == FULL)
	return true;
#elif (FLUSH_TIMING_POLICY == WATERMARK_NAIVE || FLUSH_TIMING_POLICY == WATERMARK_DOUBLE || FLUSH_TIMING_POLICY == WATERMARK_ONDEMAND)
	size_t used_ppgs_cnt = 0;
	size_t full_ppgs_cnt = 0;
	struct buffer_ppg *block;
	list_for_each_entry(block, &buf->used_ppgs, list) {
		if (block->status == VALID) {
			used_ppgs_cnt++;
			if (block->pg_idx >= buf->pg_per_ppg) {
				full_ppgs_cnt++;
			}
		}
	}
	return used_ppgs_cnt >= buf->buffer_high_watermark;
#endif
}

/*
* Select a buffer page group to flush
* Naive implementation: select the all buffer pages in the buffer when used buffer pages are more than threshold
* LRU implementation: select the least recently used buffer pages in the buffer when used buffer pages are more than threshold
*/
static inline void select_flush_buffer(struct buffer *buf)
{
	size_t flush_amount;
#if (FLUSH_TIMING_POLICY == FULL || FULL_WAIT_QUATER || FULL_WAIT_HALF)
	flush_amount = buf->used_ppgs_cnt;
#elif (FLUSH_TIMING_POLICY == HALF_NAIVE)
	flush_amount = buf->used_ppgs_cnt;
#elif (FLUSH_TIMING_POLICY == HALF_STATIC)
	flush_amount = 1;
#elif (FLUSH_TIMING_POLICY == HALF_WATERMARK)
	flush_amount = 0;

	if (buf->used_ppgs_cnt > buf->buffer_high_watermark) {
		flush_amount = 1;
	}
	else if (buf->used_ppgs_cnt > buf->buffer_low_watermark) {
		flush_amount = 2;
	}
	else {
		return;
	}
#elif (FLUSH_TIMING_POLICY == WATERMARK_ONDEMAND)
	/* IN PROGRESS */
	int needed_pages[SSD_PARTITIONS] = {0, };

	for (int i = 1; i <= nvmev_vdev->nr_sq; i++) {
		struct nvmev_submission_queue *sq = nvmev_vdev->sqes[i];
		if (!sq)
			continue;
		
		// Have to ask this about shim
		int sq_entry_id = nvmev_vdev->dbs[sq->qid * 2];
		struct nvme_command *cmd = &sq_entry(sq_entry_id);	
		uint64_t lba = cmd->rw.slba;
		uint64_t nr_lba = (cmd->rw.length + 1);
		uint64_t start_lpn = lba / buf->sec_per_pg;
		uint64_t end_lpn = (lba + nr_lba - 1) / buf->sec_per_pg;
		uint64_t size = (cmd->rw.length + 1) << LBA_BITS;

		int tmp[SSD_PARTITIONS] = {0, };
		for (uint64_t lpn = start_lpn; lpn <= end_lpn; lpn++) {
			tmp[GET_FTL_IDX(lpn)]++;
		}
		
		struct buffer_ppg *ppg = NULL;
		struct buffer_page *page = NULL;
		list_for_each_entry(ppg, &buf->used_ppgs, list) {
			if (ppg->status == VALID) {
				for (int i = 0; i < buf->pg_per_ppg; i++)  {
					if (ppg->pages[i].lpn >= start_lpn && ppg->pages[i].lpn <= end_lpn) {
						tmp[GET_FTL_IDX(ppg->pages[i].lpn)]--;
					}
				}
			}
		}

		for(int i = 0; i < SSD_PARTITIONS; i++) {
			needed_pages[i] += tmp[i];
		}
	}


#endif
	int valid_ppgs = 0;
	struct buffer_ppg *ppg;
	list_for_each_entry(ppg, &buf->used_ppgs, list) {
		
		if (ppg->status == VALID && ppg->pg_idx == buf->pg_per_ppg) {
			// ppg->status = RMW_TARGET;
			// if (--flush_amount == 0) {
			// 	break;
			// }
			valid_ppgs++;
			if (flush_amount-- >= 0) {
				ppg->status = RMW_TARGET;
			}
		}
	}

	return;
}

static inline bool last_pg_in_wordline(struct conv_ftl *conv_ftl, struct ppa *ppa)
{
	struct ssdparams *spp = &conv_ftl->ssd->sp;
	return (ppa->g.pg % spp->pgs_per_oneshotpg) == (spp->pgs_per_oneshotpg - 1);
}

static bool should_gc(struct conv_ftl *conv_ftl)
{
	return (conv_ftl->lm.free_line_cnt <= conv_ftl->cp.gc_thres_lines);
}

static inline bool should_gc_high(struct conv_ftl *conv_ftl)
{
	return conv_ftl->lm.free_line_cnt <= conv_ftl->cp.gc_thres_lines_high;
}

static inline struct ppa get_maptbl_ent(struct conv_ftl *conv_ftl, uint64_t lpn)
{
	return conv_ftl->maptbl[lpn];
}

static inline void set_maptbl_ent(struct conv_ftl *conv_ftl, uint64_t lpn, struct ppa *ppa)
{
	NVMEV_ASSERT(lpn < conv_ftl->ssd->sp.tt_pgs);
	conv_ftl->maptbl[lpn] = *ppa;
}

static uint64_t ppa2pgidx(struct conv_ftl *conv_ftl, struct ppa *ppa)
{
	struct ssdparams *spp = &conv_ftl->ssd->sp;
	uint64_t pgidx;

	NVMEV_DEBUG_VERBOSE("%s: ch:%d, lun:%d, pl:%d, blk:%d, pg:%d\n", __func__,
			ppa->g.ch, ppa->g.lun, ppa->g.pl, ppa->g.blk, ppa->g.pg);

	pgidx = ppa->g.ch * spp->pgs_per_ch + ppa->g.lun * spp->pgs_per_lun +
		ppa->g.pl * spp->pgs_per_pl + ppa->g.blk * spp->pgs_per_blk + ppa->g.pg;

	NVMEV_ASSERT(pgidx < spp->tt_pgs);

	return pgidx;
}

static inline uint64_t get_rmap_ent(struct conv_ftl *conv_ftl, struct ppa *ppa)
{
	uint64_t pgidx = ppa2pgidx(conv_ftl, ppa);

	return conv_ftl->rmap[pgidx];
}

/* set rmap[page_no(ppa)] -> lpn */
static inline void set_rmap_ent(struct conv_ftl *conv_ftl, uint64_t lpn, struct ppa *ppa)
{
	uint64_t pgidx = ppa2pgidx(conv_ftl, ppa);

	conv_ftl->rmap[pgidx] = lpn;
}

static inline int victim_line_cmp_pri(pqueue_pri_t next, pqueue_pri_t curr)
{
	return (next > curr);
}

static inline pqueue_pri_t victim_line_get_pri(void *a)
{
	return ((struct line *)a)->vpc;
}

static inline void victim_line_set_pri(void *a, pqueue_pri_t pri)
{
	((struct line *)a)->vpc = pri;
}

static inline size_t victim_line_get_pos(void *a)
{
	return ((struct line *)a)->pos;
}

static inline void victim_line_set_pos(void *a, size_t pos)
{
	((struct line *)a)->pos = pos;
}

static inline void consume_write_credit(struct conv_ftl *conv_ftl)
{
	conv_ftl->wfc.write_credits--;
}

static void foreground_gc(struct conv_ftl *conv_ftl);

static inline void check_and_refill_write_credit(struct conv_ftl *conv_ftl)
{
	struct write_flow_control *wfc = &(conv_ftl->wfc);
	if (wfc->write_credits <= 0) {
		foreground_gc(conv_ftl);

		wfc->write_credits += wfc->credits_to_refill;
	}
}

static void init_lines(struct conv_ftl *conv_ftl)
{
	struct ssdparams *spp = &conv_ftl->ssd->sp;
	struct line_mgmt *lm = &conv_ftl->lm;
	struct line *line;
	int i;

	lm->tt_lines = spp->blks_per_pl;
	NVMEV_ASSERT(lm->tt_lines == spp->tt_lines);
	lm->lines = vmalloc(sizeof(struct line) * lm->tt_lines);

	INIT_LIST_HEAD(&lm->free_line_list);
	INIT_LIST_HEAD(&lm->full_line_list);

	lm->victim_line_pq = pqueue_init(spp->tt_lines, victim_line_cmp_pri, victim_line_get_pri,
					 victim_line_set_pri, victim_line_get_pos,
					 victim_line_set_pos);

	lm->free_line_cnt = 0;
	for (i = 0; i < lm->tt_lines; i++) {
		lm->lines[i] = (struct line){
			.id = i,
			.ipc = 0,
			.vpc = 0,
			.pos = 0,
			.entry = LIST_HEAD_INIT(lm->lines[i].entry),
		};

		/* initialize all the lines as free lines */
		list_add_tail(&lm->lines[i].entry, &lm->free_line_list);
		lm->free_line_cnt++;
	}

	NVMEV_ASSERT(lm->free_line_cnt == lm->tt_lines);
	lm->victim_line_cnt = 0;
	lm->full_line_cnt = 0;
}

static void remove_lines(struct conv_ftl *conv_ftl)
{
	pqueue_free(conv_ftl->lm.victim_line_pq);
	vfree(conv_ftl->lm.lines);
}

static void init_write_flow_control(struct conv_ftl *conv_ftl)
{
	struct write_flow_control *wfc = &(conv_ftl->wfc);
	struct ssdparams *spp = &conv_ftl->ssd->sp;

	wfc->write_credits = spp->pgs_per_line;
	wfc->credits_to_refill = spp->pgs_per_line;
}

static inline void check_addr(int a, int max)
{
	NVMEV_ASSERT(a >= 0 && a < max);
}

static struct line *get_next_free_line(struct conv_ftl *conv_ftl)
{
	struct line_mgmt *lm = &conv_ftl->lm;
	struct line *curline = list_first_entry_or_null(&lm->free_line_list, struct line, entry);

	if (!curline) {
		NVMEV_ERROR("No free line left in VIRT !!!!\n");
		return NULL;
	}

	list_del_init(&curline->entry);
	lm->free_line_cnt--;
	NVMEV_DEBUG("%s: free_line_cnt %d\n", __func__, lm->free_line_cnt);
	return curline;
}

static struct write_pointer *__get_wp(struct conv_ftl *ftl, uint32_t io_type)
{
	if (io_type == USER_IO) {
		return &ftl->wp;
	} else if (io_type == GC_IO) {
		return &ftl->gc_wp;
	}

	NVMEV_ASSERT(0);
	return NULL;
}

static void prepare_write_pointer(struct conv_ftl *conv_ftl, uint32_t io_type)
{
	struct write_pointer *wp = __get_wp(conv_ftl, io_type);
	struct line *curline = get_next_free_line(conv_ftl);

	NVMEV_ASSERT(wp);
	NVMEV_ASSERT(curline);

	/* wp->curline is always our next-to-write super-block */
	*wp = (struct write_pointer){
		.curline = curline,
		.ch = 0,
		.lun = 0,
		.pg = 0,
		.blk = curline->id,
		.pl = 0,
	};
}

static void advance_write_pointer(struct conv_ftl *conv_ftl, uint32_t io_type)
{
	struct ssdparams *spp = &conv_ftl->ssd->sp;
	struct line_mgmt *lm = &conv_ftl->lm;
	struct write_pointer *wpp = __get_wp(conv_ftl, io_type);

	NVMEV_DEBUG_VERBOSE("current wpp: ch:%d, lun:%d, pl:%d, blk:%d, pg:%d\n",
			wpp->ch, wpp->lun, wpp->pl, wpp->blk, wpp->pg);

	check_addr(wpp->pg, spp->pgs_per_blk);
	wpp->pg++;
	if ((wpp->pg % spp->pgs_per_oneshotpg) != 0)
		goto out;

	wpp->pg -= spp->pgs_per_oneshotpg;
	check_addr(wpp->ch, spp->nchs);
	wpp->ch++;
	if (wpp->ch != spp->nchs)
		goto out;

	wpp->ch = 0;
	check_addr(wpp->lun, spp->luns_per_ch);
	wpp->lun++;
	/* in this case, we should go to next lun */
	if (wpp->lun != spp->luns_per_ch)
		goto out;

	wpp->lun = 0;
	/* go to next wordline in the block */
	wpp->pg += spp->pgs_per_oneshotpg;
	if (wpp->pg != spp->pgs_per_blk)
		goto out;

	wpp->pg = 0;
	/* move current line to {victim,full} line list */
	if (wpp->curline->vpc == spp->pgs_per_line) {
		/* all pgs are still valid, move to full line list */
		NVMEV_ASSERT(wpp->curline->ipc == 0);
		list_add_tail(&wpp->curline->entry, &lm->full_line_list);
		lm->full_line_cnt++;
		NVMEV_DEBUG_VERBOSE("wpp: move line to full_line_list\n");
	} else {
		NVMEV_DEBUG_VERBOSE("wpp: line is moved to victim list\n");
		NVMEV_ASSERT(wpp->curline->vpc >= 0 && wpp->curline->vpc < spp->pgs_per_line);
		/* there must be some invalid pages in this line */
		NVMEV_ASSERT(wpp->curline->ipc > 0);
		pqueue_insert(lm->victim_line_pq, wpp->curline);
		lm->victim_line_cnt++;
	}
	/* current line is used up, pick another empty line */
	check_addr(wpp->blk, spp->blks_per_pl);
	wpp->curline = get_next_free_line(conv_ftl);
	NVMEV_DEBUG_VERBOSE("wpp: got new clean line %d\n", wpp->curline->id);

	wpp->blk = wpp->curline->id;
	check_addr(wpp->blk, spp->blks_per_pl);

	/* make sure we are starting from page 0 in the super block */
	NVMEV_ASSERT(wpp->pg == 0);
	NVMEV_ASSERT(wpp->lun == 0);
	NVMEV_ASSERT(wpp->ch == 0);
	/* TODO: assume # of pl_per_lun is 1, fix later */
	NVMEV_ASSERT(wpp->pl == 0);
out:
	NVMEV_DEBUG_VERBOSE("advanced wpp: ch:%d, lun:%d, pl:%d, blk:%d, pg:%d (curline %d)\n",
			wpp->ch, wpp->lun, wpp->pl, wpp->blk, wpp->pg, wpp->curline->id);
}

static struct ppa get_new_page(struct conv_ftl *conv_ftl, uint32_t io_type)
{
	struct ppa ppa;
	struct write_pointer *wp = __get_wp(conv_ftl, io_type);

	ppa.ppa = 0;
	ppa.g.ch = wp->ch;
	ppa.g.lun = wp->lun;
	ppa.g.pg = wp->pg;
	ppa.g.blk = wp->blk;
	ppa.g.pl = wp->pl;

	NVMEV_ASSERT(ppa.g.pl == 0);

	return ppa;
}

static void init_maptbl(struct conv_ftl *conv_ftl)
{
	int i;
	struct ssdparams *spp = &conv_ftl->ssd->sp;

	conv_ftl->maptbl = vmalloc(sizeof(struct ppa) * spp->tt_pgs);
	for (i = 0; i < spp->tt_pgs; i++) {
		conv_ftl->maptbl[i].ppa = UNMAPPED_PPA;
	}
}

static void remove_maptbl(struct conv_ftl *conv_ftl)
{
	vfree(conv_ftl->maptbl);
}

static void init_rmap(struct conv_ftl *conv_ftl)
{
	int i;
	struct ssdparams *spp = &conv_ftl->ssd->sp;

	conv_ftl->rmap = vmalloc(sizeof(uint64_t) * spp->tt_pgs);
	for (i = 0; i < spp->tt_pgs; i++) {
		conv_ftl->rmap[i] = INVALID_LPN;
	}
}

static void remove_rmap(struct conv_ftl *conv_ftl)
{
	vfree(conv_ftl->rmap);
}

static void conv_init_ftl(struct conv_ftl *conv_ftl, struct convparams *cpp, struct ssd *ssd)
{
	/*copy convparams*/
	conv_ftl->cp = *cpp;

	conv_ftl->ssd = ssd;

	/* initialize maptbl */
	init_maptbl(conv_ftl); // mapping table

	/* initialize rmap */
	init_rmap(conv_ftl); // reverse mapping table (?)

	/* initialize all the lines */
	init_lines(conv_ftl);

	/* initialize write pointer, this is how we allocate new pages for writes */
	prepare_write_pointer(conv_ftl, USER_IO);
	prepare_write_pointer(conv_ftl, GC_IO);

	init_write_flow_control(conv_ftl);

	NVMEV_INFO("Init FTL instance with %d channels (%ld pages)\n", conv_ftl->ssd->sp.nchs,
		   conv_ftl->ssd->sp.tt_pgs);

	return;
}

static void conv_remove_ftl(struct conv_ftl *conv_ftl)
{
	remove_lines(conv_ftl);
	remove_rmap(conv_ftl);
	remove_maptbl(conv_ftl);
}

static void conv_init_params(struct convparams *cpp)
{
	cpp->op_area_pcent = OP_AREA_PERCENT;
	cpp->gc_thres_lines = 2; /* Need only two lines.(host write, gc)*/
	cpp->gc_thres_lines_high = 2; /* Need only two lines.(host write, gc)*/
	cpp->enable_gc_delay = 0;
	cpp->pba_pcent = (int)((1 + cpp->op_area_pcent) * 100);
}

void conv_init_namespace(struct nvmev_ns *ns, uint32_t id, uint64_t size, void *mapped_addr,
			 uint32_t cpu_nr_dispatcher)
{
	struct ssdparams spp;
	struct convparams cpp;
	struct conv_ftl *conv_ftls;
	struct ssd *ssd;
	uint32_t i;
	const uint32_t nr_parts = SSD_PARTITIONS;

	ssd_init_params(&spp, size, nr_parts);
	conv_init_params(&cpp);

	conv_ftls = kmalloc(sizeof(struct conv_ftl) * nr_parts, GFP_KERNEL);

	for (i = 0; i < nr_parts; i++) {
		ssd = kmalloc(sizeof(struct ssd), GFP_KERNEL);
		ssd_init(ssd, &spp, cpu_nr_dispatcher);
		conv_init_ftl(&conv_ftls[i], &cpp, ssd);
	}

	conv_ftls[0].ssd->write_buffer = kmalloc(sizeof(struct buffer), GFP_KERNEL);
	buffer_init(conv_ftls[0].ssd->write_buffer, spp.write_buffer_size, &spp);

	/* PCIe is shared by all instances. But write buffer is NOT.(bae)*/
	for (i = 1; i < nr_parts; i++) {
		kfree(conv_ftls[i].ssd->pcie->perf_model);
		kfree(conv_ftls[i].ssd->pcie);

		conv_ftls[i].ssd->pcie = conv_ftls[0].ssd->pcie;
		conv_ftls[i].ssd->write_buffer = conv_ftls[0].ssd->write_buffer;
	}

	ns->id = id;
	ns->csi = NVME_CSI_NVM;
	ns->nr_parts = nr_parts;
	ns->ftls = (void *)conv_ftls;
	ns->size = (uint64_t)((size * 100) / cpp.pba_pcent);
	ns->mapped = mapped_addr;
	/*register io command handler*/
	ns->proc_io_cmd = conv_proc_nvme_io_cmd;

	NVMEV_INFO("FTL physical space: %lld, logical space: %lld (physical/logical * 100 = %d)\n",
		   size, ns->size, cpp.pba_pcent);

	return;
}

void conv_remove_namespace(struct nvmev_ns *ns)
{
	struct conv_ftl *conv_ftls = (struct conv_ftl *)ns->ftls;
	const uint32_t nr_parts = SSD_PARTITIONS;
	uint32_t i;

	/* PCIe, Write buffer are shared by all instances*/
	for (i = 1; i < nr_parts; i++) {
		/*
		 * These were freed from conv_init_namespace() already.
		 * Mark these NULL so that ssd_remove() skips it.
		 */
		conv_ftls[i].ssd->pcie = NULL;
		conv_ftls[i].ssd->write_buffer = NULL;
		conv_ftls[i].ssd->write_buffer = NULL;
	}

	for (i = 0; i < nr_parts; i++) {
		conv_remove_ftl(&conv_ftls[i]);
		ssd_remove(conv_ftls[i].ssd);
		kfree(conv_ftls[i].ssd);
	}

	kfree(conv_ftls);
	ns->ftls = NULL;
}

static inline bool valid_ppa(struct conv_ftl *conv_ftl, struct ppa *ppa)
{
	struct ssdparams *spp = &conv_ftl->ssd->sp;
	int ch = ppa->g.ch;
	int lun = ppa->g.lun;
	int pl = ppa->g.pl;
	int blk = ppa->g.blk;
	int pg = ppa->g.pg;
	//int sec = ppa->g.sec;

	if (ch < 0 || ch >= spp->nchs)
		return false;
	if (lun < 0 || lun >= spp->luns_per_ch)
		return false;
	if (pl < 0 || pl >= spp->pls_per_lun)
		return false;
	if (blk < 0 || blk >= spp->blks_per_pl)
		return false;
	if (pg < 0 || pg >= spp->pgs_per_blk)
		return false;

	return true;
}

static inline bool valid_lpn(struct conv_ftl *conv_ftl, uint64_t lpn)
{
	return (lpn < conv_ftl->ssd->sp.tt_pgs);
}

static inline bool mapped_ppa(struct ppa *ppa)
{
	return !(ppa->ppa == UNMAPPED_PPA);
}

static inline struct line *get_line(struct conv_ftl *conv_ftl, struct ppa *ppa)
{
	return &(conv_ftl->lm.lines[ppa->g.blk]);
}

/* update SSD status about one page from PG_VALID -> PG_VALID */
static void mark_page_invalid(struct conv_ftl *conv_ftl, struct ppa *ppa)
{
	struct ssdparams *spp = &conv_ftl->ssd->sp;
	struct line_mgmt *lm = &conv_ftl->lm;
	struct nand_block *blk = NULL;
	struct nand_page *pg = NULL;
	bool was_full_line = false;
	struct line *line;

	/* update corresponding page status */
	pg = get_pg(conv_ftl->ssd, ppa);
	NVMEV_ASSERT(pg->status == PG_VALID);
	pg->status = PG_INVALID;

	/* update corresponding block status */
	blk = get_blk(conv_ftl->ssd, ppa);
	NVMEV_ASSERT(blk->ipc >= 0 && blk->ipc < spp->pgs_per_blk);
	blk->ipc++;
	NVMEV_ASSERT(blk->vpc > 0 && blk->vpc <= spp->pgs_per_blk);
	blk->vpc--;

	/* update corresponding line status */
	line = get_line(conv_ftl, ppa);
	NVMEV_ASSERT(line->ipc >= 0 && line->ipc < spp->pgs_per_line);
	if (line->vpc == spp->pgs_per_line) {
		NVMEV_ASSERT(line->ipc == 0);
		was_full_line = true;
	}
	line->ipc++;
	NVMEV_ASSERT(line->vpc > 0 && line->vpc <= spp->pgs_per_line);
	/* Adjust the position of the victime line in the pq under over-writes */
	if (line->pos) {
		/* Note that line->vpc will be updated by this call */
		pqueue_change_priority(lm->victim_line_pq, line->vpc - 1, line);
	} else {
		line->vpc--;
	}

	if (was_full_line) {
		/* move line: "full" -> "victim" */
		list_del_init(&line->entry);
		lm->full_line_cnt--;
		pqueue_insert(lm->victim_line_pq, line);
		lm->victim_line_cnt++;
	}
}

static void mark_page_valid(struct conv_ftl *conv_ftl, struct ppa *ppa)
{
	struct ssdparams *spp = &conv_ftl->ssd->sp;
	struct nand_block *blk = NULL;
	struct nand_page *pg = NULL;
	struct line *line;

	/* update page status */
	pg = get_pg(conv_ftl->ssd, ppa);
	NVMEV_ASSERT(pg->status == PG_FREE);
	pg->status = PG_VALID;

	/* update corresponding block status */
	blk = get_blk(conv_ftl->ssd, ppa);
	NVMEV_ASSERT(blk->vpc >= 0 && blk->vpc < spp->pgs_per_blk);
	blk->vpc++;

	/* update corresponding line status */
	line = get_line(conv_ftl, ppa);
	NVMEV_ASSERT(line->vpc >= 0 && line->vpc < spp->pgs_per_line);
	line->vpc++;
}

static void mark_block_free(struct conv_ftl *conv_ftl, struct ppa *ppa)
{
	struct ssdparams *spp = &conv_ftl->ssd->sp;
	struct nand_block *blk = get_blk(conv_ftl->ssd, ppa);
	struct nand_page *pg = NULL;
	int i;

	for (i = 0; i < spp->pgs_per_blk; i++) {
		/* reset page status */
		pg = &blk->pg[i];
		NVMEV_ASSERT(pg->nsecs == spp->secs_per_pg);
		pg->status = PG_FREE;
	}

	/* reset block status */
	NVMEV_ASSERT(blk->npgs == spp->pgs_per_blk);
	blk->ipc = 0;
	blk->vpc = 0;
	blk->erase_cnt++;
}

static void gc_read_page(struct conv_ftl *conv_ftl, struct ppa *ppa)
{
	struct ssdparams *spp = &conv_ftl->ssd->sp;
	struct convparams *cpp = &conv_ftl->cp;
	/* advance conv_ftl status, we don't care about how long it takes */
	if (cpp->enable_gc_delay) {
		struct nand_cmd gcr = {
			.type = GC_IO,
			.cmd = NAND_READ,
			.stime = 0,
			.xfer_size = spp->pgsz,
			.interleave_pci_dma = false,
			.ppa = ppa,
		};
		ssd_advance_nand(conv_ftl->ssd, &gcr);
	}
}

/* move valid page data (already in DRAM) from victim line to a new page */
static uint64_t gc_write_page(struct conv_ftl *conv_ftl, struct ppa *old_ppa)
{
	struct ssdparams *spp = &conv_ftl->ssd->sp;
	struct convparams *cpp = &conv_ftl->cp;
	struct ppa new_ppa;
	uint64_t lpn = get_rmap_ent(conv_ftl, old_ppa);

	NVMEV_ASSERT(valid_lpn(conv_ftl, lpn));
	new_ppa = get_new_page(conv_ftl, GC_IO);
	/* update maptbl */
	set_maptbl_ent(conv_ftl, lpn, &new_ppa);
	/* update rmap */
	set_rmap_ent(conv_ftl, lpn, &new_ppa);

	mark_page_valid(conv_ftl, &new_ppa);

	/* need to advance the write pointer here */
	advance_write_pointer(conv_ftl, GC_IO);

	if (cpp->enable_gc_delay) {
		struct nand_cmd gcw = {
			.type = GC_IO,
			.cmd = NAND_NOP,
			.stime = 0,
			.interleave_pci_dma = false,
			.ppa = &new_ppa,
		};
		if (last_pg_in_wordline(conv_ftl, &new_ppa)) {
			gcw.cmd = NAND_WRITE;
			gcw.xfer_size = spp->pgsz * spp->pgs_per_oneshotpg;
		}

		ssd_advance_nand(conv_ftl->ssd, &gcw);
	}

	/* advance per-ch gc_endtime as well */
#if 0
	new_ch = get_ch(conv_ftl, &new_ppa);
	new_ch->gc_endtime = new_ch->next_ch_avail_time;

	new_lun = get_lun(conv_ftl, &new_ppa);
	new_lun->gc_endtime = new_lun->next_lun_avail_time;
#endif

	return 0;
}

static struct line *select_victim_line(struct conv_ftl *conv_ftl, bool force)
{
	struct ssdparams *spp = &conv_ftl->ssd->sp;
	struct line_mgmt *lm = &conv_ftl->lm;
	struct line *victim_line = NULL;

	victim_line = pqueue_peek(lm->victim_line_pq);
	if (!victim_line) {
		return NULL;
	}

	if (!force && (victim_line->vpc > (spp->pgs_per_line / 8))) {
		return NULL;
	}

	pqueue_pop(lm->victim_line_pq);
	victim_line->pos = 0;
	lm->victim_line_cnt--;

	/* victim_line is a danggling node now */
	return victim_line;
}

/* here ppa identifies the block we want to clean */
static void clean_one_block(struct conv_ftl *conv_ftl, struct ppa *ppa)
{
	struct ssdparams *spp = &conv_ftl->ssd->sp;
	struct nand_page *pg_iter = NULL;
	int cnt = 0;
	int pg;

	for (pg = 0; pg < spp->pgs_per_blk; pg++) {
		ppa->g.pg = pg;
		pg_iter = get_pg(conv_ftl->ssd, ppa);
		/* there shouldn't be any free page in victim blocks */
		NVMEV_ASSERT(pg_iter->status != PG_FREE);
		if (pg_iter->status == PG_VALID) {
			gc_read_page(conv_ftl, ppa);
			/* delay the maptbl update until "write" happens */
			gc_write_page(conv_ftl, ppa);
			cnt++;
		}
	}

	NVMEV_ASSERT(get_blk(conv_ftl->ssd, ppa)->vpc == cnt);
}

/* here ppa identifies the block we want to clean */
static void clean_one_flashpg(struct conv_ftl *conv_ftl, struct ppa *ppa)
{
	struct ssdparams *spp = &conv_ftl->ssd->sp;
	struct convparams *cpp = &conv_ftl->cp;
	struct nand_page *pg_iter = NULL;
	int cnt = 0, i = 0;
	uint64_t completed_time = 0;
	struct ppa ppa_copy = *ppa;

	for (i = 0; i < spp->pgs_per_flashpg; i++) {
		pg_iter = get_pg(conv_ftl->ssd, &ppa_copy);
		/* there shouldn't be any free page in victim blocks */
		NVMEV_ASSERT(pg_iter->status != PG_FREE);
		if (pg_iter->status == PG_VALID)
			cnt++;

		ppa_copy.g.pg++;
	}

	ppa_copy = *ppa;

	if (cnt <= 0)
		return;

	if (cpp->enable_gc_delay) {
		struct nand_cmd gcr = {
			.type = GC_IO,
			.cmd = NAND_READ,
			.stime = 0,
			.xfer_size = spp->pgsz * cnt,
			.interleave_pci_dma = false,
			.ppa = &ppa_copy,
		};
		completed_time = ssd_advance_nand(conv_ftl->ssd, &gcr);
	}

	for (i = 0; i < spp->pgs_per_flashpg; i++) {
		pg_iter = get_pg(conv_ftl->ssd, &ppa_copy);

		/* there shouldn't be any free page in victim blocks */
		if (pg_iter->status == PG_VALID) {
			/* delay the maptbl update until "write" happens */
			gc_write_page(conv_ftl, &ppa_copy);
		}

		ppa_copy.g.pg++;
	}
}

static void mark_line_free(struct conv_ftl *conv_ftl, struct ppa *ppa)
{
	struct line_mgmt *lm = &conv_ftl->lm;
	struct line *line = get_line(conv_ftl, ppa);
	line->ipc = 0;
	line->vpc = 0;
	/* move this line to free line list */
	list_add_tail(&line->entry, &lm->free_line_list);
	lm->free_line_cnt++;
}

static int do_gc(struct conv_ftl *conv_ftl, bool force)
{
	struct line *victim_line = NULL;
	struct ssdparams *spp = &conv_ftl->ssd->sp;
	struct ppa ppa;
	int flashpg;

	victim_line = select_victim_line(conv_ftl, force);
	if (!victim_line) {
		return -1;
	}

	ppa.g.blk = victim_line->id;
	NVMEV_DEBUG_VERBOSE("GC-ing line:%d,ipc=%d(%d),victim=%d,full=%d,free=%d\n", ppa.g.blk,
		    victim_line->ipc, victim_line->vpc, conv_ftl->lm.victim_line_cnt,
		    conv_ftl->lm.full_line_cnt, conv_ftl->lm.free_line_cnt);

	conv_ftl->wfc.credits_to_refill = victim_line->ipc;

	/* copy back valid data */
	for (flashpg = 0; flashpg < spp->flashpgs_per_blk; flashpg++) {
		int ch, lun;

		ppa.g.pg = flashpg * spp->pgs_per_flashpg;
		for (ch = 0; ch < spp->nchs; ch++) {
			for (lun = 0; lun < spp->luns_per_ch; lun++) {
				struct nand_lun *lunp;

				ppa.g.ch = ch;
				ppa.g.lun = lun;
				ppa.g.pl = 0;
				lunp = get_lun(conv_ftl->ssd, &ppa);
				clean_one_flashpg(conv_ftl, &ppa);

				if (flashpg == (spp->flashpgs_per_blk - 1)) {
					struct convparams *cpp = &conv_ftl->cp;

					mark_block_free(conv_ftl, &ppa);

					if (cpp->enable_gc_delay) {
						struct nand_cmd gce = {
							.type = GC_IO,
							.cmd = NAND_ERASE,
							.stime = 0,
							.interleave_pci_dma = false,
							.ppa = &ppa,
						};
						ssd_advance_nand(conv_ftl->ssd, &gce);
					}

					lunp->gc_endtime = lunp->next_lun_avail_time;
				}
			}
		}
	}

	/* update line status */
	mark_line_free(conv_ftl, &ppa);

	return 0;
}

static void foreground_gc(struct conv_ftl *conv_ftl)
{
	if (should_gc_high(conv_ftl)) {
		NVMEV_DEBUG_VERBOSE("should_gc_high passed");
		/* perform GC here until !should_gc(conv_ftl) */
		do_gc(conv_ftl, true);
	}
}

static bool is_same_flash_page(struct conv_ftl *conv_ftl, struct ppa ppa1, struct ppa ppa2)
{
	struct ssdparams *spp = &conv_ftl->ssd->sp;
	uint32_t ppa1_page = ppa1.g.pg / spp->pgs_per_flashpg;
	uint32_t ppa2_page = ppa2.g.pg / spp->pgs_per_flashpg;

	return (ppa1.h.blk_in_ssd == ppa2.h.blk_in_ssd) && (ppa1_page == ppa2_page);
}

static bool conv_read(struct nvmev_ns *ns, struct nvmev_request *req, struct nvmev_result *ret)
{
	struct conv_ftl *conv_ftls = (struct conv_ftl *)ns->ftls;
	struct conv_ftl *conv_ftl = &conv_ftls[0];
	struct ssd *ssd = conv_ftl->ssd;
	/* wbuf and spp are shared by all instances*/
	struct buffer *wbuf = ssd->write_buffer;
	struct ssdparams *spp = &conv_ftl->ssd->sp;

	struct nvme_command *cmd = req->cmd;
	uint64_t lba = cmd->rw.slba;
	uint64_t nr_lba = (cmd->rw.length + 1);
	uint64_t start_lpn = lba / spp->secs_per_pg;
	uint64_t end_lpn = (lba + nr_lba - 1) / spp->secs_per_pg;
	uint64_t nsecs_start = req->nsecs_start;
	uint64_t nsecs_completed, nsecs_latest = nsecs_start;
	uint32_t xfer_size, i;
	uint32_t nr_parts = ns->nr_parts;
	uint32_t ssd_read_cnt = 0;
	size_t buffered_block_cnt = 0;
	int pgs_per_flashpg = spp->pgs_per_flashpg;

	struct ppa prev_ppa;
	struct nand_cmd srd = {
		.type = USER_IO,
		.cmd = NAND_READ,
		.stime = nsecs_start,
		.interleave_pci_dma = true,
	};

	NVMEV_ASSERT(conv_ftls);
	NVMEV_DEBUG_VERBOSE("%s: start_lpn=%lld, len=%lld, end_lpn=%lld", __func__, start_lpn, nr_lba, end_lpn);
	if ((end_lpn / nr_parts) >= spp->tt_pgs) {
		NVMEV_ERROR("%s: lpn passed FTL range (start_lpn=%lld > tt_pgs=%ld)\n", __func__,
			    start_lpn, spp->tt_pgs);
		return false;
	}

	// interleaving read requests over all parts
	for (i = 0; (i < nr_parts) && (start_lpn <= end_lpn); i++, start_lpn += pgs_per_flashpg) {
		xfer_size = 0;
		int ftl_idx = GET_FTL_IDX(start_lpn);
		conv_ftl = &conv_ftls[ftl_idx];
		prev_ppa = get_maptbl_ent(conv_ftl, LOCAL_LPN(start_lpn));

		uint64_t local_start_lpn = start_lpn;
		
		// jump to the next flash page of the current part(4 flash pages)
		for (; local_start_lpn <= end_lpn; local_start_lpn += pgs_per_flashpg * nr_parts) {
			// local_end_lpn is the last lpn in the current flash page or the end of the request
			uint64_t local_end_lpn = min(end_lpn, local_start_lpn + pgs_per_flashpg - 1);
			for (uint64_t lpn = local_start_lpn; lpn <= local_end_lpn; lpn++) {
				uint64_t local_lpn = LOCAL_LPN(lpn);

				struct ppa cur_ppa = get_maptbl_ent(conv_ftl, local_lpn);
				if (!mapped_ppa(&cur_ppa) || !valid_ppa(conv_ftl, &cur_ppa)) {
					NVMEV_DEBUG_VERBOSE("lpn 0x%llx not mapped to valid ppa\n", local_lpn);
					NVMEV_DEBUG_VERBOSE("Invalid ppa,ch:%d,lun:%d,blk:%d,pl:%d,pg:%d\n",
							    cur_ppa.g.ch, cur_ppa.g.lun, cur_ppa.g.blk,
							    cur_ppa.g.pl, cur_ppa.g.pg);
					continue;
				}

				// if the lpn is in the write buffer, advance the write buffer, not the NAND
				if (buffer_search(wbuf, lpn) != NULL) {
					nsecs_completed = ssd_advance_write_buffer(conv_ftl->ssd, nsecs_start, LBA_TO_BYTE(nr_lba));
					nsecs_latest = max(nsecs_completed, nsecs_latest);
					continue;
				}

				// aggregate read io in same flash page
				if (mapped_ppa(&prev_ppa) &&
				    is_same_flash_page(conv_ftl, cur_ppa, prev_ppa) && (lpn != start_lpn)) {
					xfer_size += spp->pgsz;
					continue;
				}

				if (xfer_size > 0) {
					srd.xfer_size = xfer_size;
					srd.ppa = &prev_ppa;
					if (xfer_size <= KB(4)) {
						srd.stime = spp->fw_4kb_rd_lat + nsecs_start;
					} else {
						srd.stime = spp->fw_rd_lat + nsecs_start;
					}
					// NVMEV_INFO("FW Read Latency: %llu\n", srd.stime - nsecs_start);
					// NVMEV_INFO("Read Occur: %d, %d, %d, %d, %d - xfer size: %u", prev_ppa.g.ch, prev_ppa.g.lun, prev_ppa.g.blk, prev_ppa.g.pl, prev_ppa.g.pg, xfer_size);
					nsecs_completed = ssd_advance_nand(conv_ftl->ssd, &srd);
					nsecs_latest = max(nsecs_completed, nsecs_latest);
				}

				if (spp->pgsz > LBA_TO_BYTE(nr_lba)) {
					// single page read, yet smaller than mapping page size
					xfer_size = LBA_TO_BYTE(nr_lba);
				} else {
					xfer_size = spp->pgsz;
				}
				prev_ppa = cur_ppa;
			}

			if (xfer_size > 0) {
				srd.xfer_size = xfer_size;
				srd.ppa = &prev_ppa;
				if (xfer_size <= KB(4)) {
					srd.stime = spp->fw_4kb_rd_lat + nsecs_start;
				} else {
					srd.stime = spp->fw_rd_lat + nsecs_start;
				}
				// NVMEV_INFO("FW Read Latency: %llu\n", srd.stime - nsecs_start);
				// NVMEV_INFO("Read Occur: %d, %d, %d, %d, %d - xfer size: %u", prev_ppa.g.ch, prev_ppa.g.lun, prev_ppa.g.blk, prev_ppa.g.pl, prev_ppa.g.pg, xfer_size);
				nsecs_completed = ssd_advance_nand(conv_ftl->ssd, &srd);
				nsecs_latest = max(nsecs_completed, nsecs_latest);
			}
		}
	}
	
	ret->nsecs_target = nsecs_latest;
	ret->status = NVME_SC_SUCCESS;

	// NVMEV_INFO("Total Read Latency: %llu\n", nsecs_latest - nsecs_start);

	return true;
}

static uint64_t conv_rmw(struct nvmev_ns *ns, struct nvmev_request *req, uint64_t nsecs_rmw_start)
{
	// NVMEV_INFO("RMW Start\n");
	struct conv_ftl *conv_ftls = (struct conv_ftl *)ns->ftls;
	struct conv_ftl *conv_ftl = &conv_ftls[0];
	struct ssd *ssd = conv_ftl->ssd;
	/* wbuf and spp are shared by all instances*/
	struct buffer *wbuf = ssd->write_buffer;
	struct ssdparams *spp = &conv_ftl->ssd->sp;
	uint64_t nsecs_result = nsecs_rmw_start;

	struct nand_cmd swr = {
		.type = USER_IO,
		.cmd = NAND_WRITE,
		.interleave_pci_dma = false,
		.xfer_size = spp->pgsz,
		.stime = nsecs_rmw_start
	};

	struct nand_cmd srd = {
		.type = USER_IO,
		.cmd = NAND_READ,
		.interleave_pci_dma = false,
		.xfer_size = spp->pgsz,
	};

	/* read phase of read-modify-write operation fill empty cell of write buffer */
	// NVMEV_INFO("Flush buffer(%d) free_ppgs: %lu, used_ppgs: %lu\n", wbuf->ftl_idx,
	// 	    list_count_nodes(&wbuf->free_ppgs), list_count_nodes(&wbuf->used_ppgs));
	struct buffer_ppg *ppg;
	struct buffer_page *page;
	struct ppa prev_ppa;
	struct ppa ppa;

	list_for_each_entry(ppg, &wbuf->used_ppgs, list) {
		if(ppg->status != RMW_TARGET) {
			continue;
		}
		
		ppg->status = FLUSHING;
		wbuf->used_ppgs_cnt--;
		wbuf->flushing_ppgs_cnt++;
		
		uint64_t nsecs_completed = nsecs_rmw_start;
		uint64_t nsecs_write_start = nsecs_rmw_start;
		uint64_t lpn = INVALID_LPN;
		uint64_t local_lpn = INVALID_LPN;
		int32_t xfer_size = 0;
		conv_ftl = &conv_ftls[ppg->ftl_idx];

		if (ppg->full_pages_cnt < wbuf->pg_per_ppg) {
			prev_ppa = get_maptbl_ent(conv_ftl, LOCAL_LPN(ppg->pages[0].lpn));

			for (size_t j = 0; j < wbuf->pg_per_ppg; j++) {
				page = &ppg->pages[j];
				lpn = page->lpn;
				local_lpn = LOCAL_LPN(lpn);
				ppa = get_maptbl_ent(conv_ftl, local_lpn);

				if (!mapped_ppa(&ppa) || !valid_ppa(conv_ftl, &ppa)) {
					continue;
				}

				if (page->free_secs > 0) {
					if (is_same_flash_page(conv_ftl, ppa, prev_ppa)) {
						xfer_size += spp->pgsz;
						continue;
					} 
						
					if (xfer_size > 0) {
						srd.xfer_size = xfer_size;
						srd.ppa = &prev_ppa;
						nsecs_completed = ssd_advance_nand(conv_ftl->ssd, &srd);
						nsecs_write_start = max(nsecs_completed, nsecs_write_start);
					}
						
					xfer_size = spp->pgsz;
				}

				prev_ppa = ppa;
			}
		}

		swr.stime = nsecs_write_start;

		/* Assumption: all pages in physical buffer page */
		for (size_t j = 0; j < wbuf->pg_per_ppg; j++) {
			struct buffer_page *page = &ppg->pages[j];
			uint64_t lpn = ppg->pages[j].lpn;

			/* check if the block is valid */
			if (lpn == INVALID_LPN) {
				continue;
			}

			uint64_t local_lpn = LOCAL_LPN(lpn);
			ppa = get_maptbl_ent(conv_ftl, local_lpn);

			if (mapped_ppa(&ppa)) {
				mark_page_invalid(conv_ftl, &ppa);
				set_rmap_ent(conv_ftl, INVALID_LPN, &ppa);
			}

			/* new write */
			ppa = get_new_page(conv_ftl, USER_IO);
			/* update maptbl */
			set_maptbl_ent(conv_ftl, local_lpn, &ppa);
			NVMEV_DEBUG("%s: got new ppa %lld, ", __func__, ppa2pgidx(conv_ftl, &ppa));
			/* update rmap */
			set_rmap_ent(conv_ftl, local_lpn, &ppa);

			mark_page_valid(conv_ftl, &ppa);

			/* need to advance the write pointer here */
			advance_write_pointer(conv_ftl, USER_IO);
				
			consume_write_credit(conv_ftl);
			check_and_refill_write_credit(conv_ftl);
		}

		swr.ppa = &ppa;
		swr.xfer_size = wbuf->ppg_size;
		nsecs_completed = ssd_advance_nand(conv_ftl->ssd, &swr);
		nsecs_result = max(nsecs_completed, nsecs_result);
		ppg->complete_time = nsecs_completed;

		schedule_internal_operation(req->sq_id, nsecs_completed, wbuf);

		nvmev_vdev->device_write += wbuf->ppg_size;
	}

	return nsecs_result;
}

static bool conv_write(struct nvmev_ns *ns, struct nvmev_request *req, struct nvmev_result *ret)
{
	struct conv_ftl *conv_ftls = (struct conv_ftl *)ns->ftls;
	struct conv_ftl *conv_ftl = &conv_ftls[0];

	/* wbuf and spp are shared by all instances */
	struct ssdparams *spp = &conv_ftl->ssd->sp;
	struct ssd *ssd = conv_ftl->ssd;
	struct buffer *wbuf = ssd->write_buffer;

	struct nvme_command *cmd = req->cmd;
	uint64_t lba = cmd->rw.slba;
	uint64_t nr_lba = (cmd->rw.length + 1);
	uint64_t start_lpn = lba / spp->secs_per_pg;
	uint64_t start_offset = lba % spp->secs_per_pg;
	uint64_t end_lpn = (lba + nr_lba - 1) / spp->secs_per_pg;
	uint64_t size = (cmd->rw.length + 1) << LBA_BITS;

	uint64_t lpn;
	uint32_t nr_parts = ns->nr_parts;
	int pgs_per_flashpg = spp->pgs_per_flashpg;

	uint64_t nsecs_start = req->nsecs_start;
	uint64_t nsecs_write_buffer;
	uint64_t nsecs_completed;
	uint64_t nsecs_latest = nsecs_start;
	uint64_t nsecs_xfer_completed;

	//check actual latency
	uint64_t read_lat = 0;
	uint64_t buffer_lat = 0;
	uint64_t write_lat = 0;

	// if (local_clock() - time > 100000) {
	// 	while (!spin_trylock(&wbuf->lock))
	// 		;

	// 	int free_secs = 0;
	// 	int total_secs = spp->write_buffer_size / spp->secsz;

	// 	struct buffer_ppg *ppg;
	// 	list_for_each_entry(ppg, &wbuf->used_ppgs, list) {
	// 		for (int i = 0; i < wbuf->pg_per_ppg; i++) {
	// 			free_secs += ppg->pages[i].free_secs;
	// 		}
	// 	}

	// 	free_secs += list_count_nodes(&wbuf->free_ppgs) * wbuf->sec_per_pg * wbuf->pg_per_ppg;

	// 	int utilized_ratio = ((total_secs - free_secs) * 100) / total_secs;
	// 	NVMEV_INFO("Buffer Utilization Ratio: %d%%\n", utilized_ratio);
	// 	time = local_clock();

	// 	spin_unlock(&wbuf->lock);
	// }
	
	NVMEV_DEBUG_VERBOSE("%s: start_lpn=%lld, len=%lld, end_lpn=%lld", __func__, start_lpn, nr_lba, end_lpn);
	if ((end_lpn / nr_parts) >= spp->tt_pgs) {
		NVMEV_ERROR("%s: lpn passed FTL range (start_lpn=%lld > tt_pgs=%ld)\n",
				__func__, start_lpn, spp->tt_pgs);
		return false;
	}

	if (!buffer_allocatable_check(wbuf, start_lpn, end_lpn, start_offset, size)){
		NVMEV_DEBUG("%s: buffer_allocate failed\n", __func__);
		// full_waiting = true;
		time = local_clock();
		while (!spin_trylock(&wbuf->lock))
			;

		if (check_flush_buffer_allocate_fail(wbuf)) {
			// NVMEV_INFO("Back RMW Start - Buffer Status: Free %ld, Flushing %d, Used %d, Utilization Ratio %d%%\n", list_count_nodes(&wbuf->free_ppgs), flushing_ppgs, used_ppgs, utilized_ratio);
			select_flush_buffer(wbuf);
			conv_rmw(ns, req, nsecs_start);
		}

		spin_unlock(&wbuf->lock);

		return false;
	}

	// NVMEV_INFO("start_lpn=%lld, len=%lld, end_lpn=%lld, delay=%lld", start_lpn, nr_lba, end_lpn, local_clock() - time);
	// time = local_clock();
	buffer_allocate(wbuf, start_lpn, end_lpn, start_offset, size);

	nvmev_vdev->user_write += size;

	nsecs_write_buffer =
		ssd_advance_write_buffer(ssd, nsecs_latest, LBA_TO_BYTE(nr_lba));

	// NVMEV_INFO("Write Buffer Latency: %llu\n", nsecs_write_buffer - nsecs_start);

	nsecs_latest = max(nsecs_write_buffer, nsecs_latest);
	nsecs_xfer_completed = nsecs_latest;

	while (!spin_trylock(&wbuf->lock))
		;

	/* Flush full pages */
	conv_rmw(ns, req, nsecs_start);

	/* Check we need RMW */
	if (check_flush_buffer(wbuf)) {
		// NVMEV_INFO("Front RMW Start - Buffer Status: Free %ld, Flushing %d, Used %d, Utilization Ratio %d%%\n", list_count_nodes(&wbuf->free_ppgs), flushing_ppgs, used_ppgs, utilized_ratio);
		select_flush_buffer(wbuf);
		nsecs_latest = max(conv_rmw(ns, req, nsecs_xfer_completed), nsecs_latest);
	}

	spin_unlock(&wbuf->lock);

	if ((cmd->rw.control & NVME_RW_FUA) || (spp->write_early_completion == 0)) {
		/* Wait all flash operations */
		ret->nsecs_target = nsecs_latest;
	} else {
		/* Early completion */
		ret->nsecs_target = nsecs_xfer_completed;
	}
	ret->status = NVME_SC_SUCCESS;

	// NVMEV_INFO("NAND Write Latency: %llu\n", nsecs_latest - nsecs_xfer_completed);
	// NVMEV_INFO("Total Write Latency: %llu\n", ret->nsecs_target - nsecs_start);

	return true;
} 

static void conv_flush(struct nvmev_ns *ns, struct nvmev_request *req, struct nvmev_result *ret)
{
	uint64_t start, latest;
	uint32_t i;
	struct conv_ftl *conv_ftls = (struct conv_ftl *)ns->ftls;

	start = local_clock();
	latest = start;
	for (i = 0; i < ns->nr_parts; i++) {
		latest = max(latest, ssd_next_idle_time(conv_ftls[i].ssd));
	}

	NVMEV_DEBUG_VERBOSE("%s: latency=%llu\n", __func__, latest - start);

	ret->status = NVME_SC_SUCCESS;
	ret->nsecs_target = latest;
	return;
}

bool conv_proc_nvme_io_cmd(struct nvmev_ns *ns, struct nvmev_request *req, struct nvmev_result *ret)
{
	struct nvme_command *cmd = req->cmd;

	NVMEV_ASSERT(ns->csi == NVME_CSI_NVM);

	switch (cmd->common.opcode) {
	case nvme_cmd_write:
		if (!conv_write(ns, req, ret))
			return false;
		break;
	case nvme_cmd_read:
		if (!conv_read(ns, req, ret))
			return false;
		break;
	case nvme_cmd_flush:
		conv_flush(ns, req, ret);
		break;
	default:
		NVMEV_ERROR("%s: command not implemented: %s (0x%x)\n", __func__,
				nvme_opcode_string(cmd->common.opcode), cmd->common.opcode);
		break;
	}

	return true;
}
