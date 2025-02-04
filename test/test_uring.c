/*
 * ssd_write_bw.c
 *
 * io_uring을 사용하여 SSD write bandwidth를 측정하는 프로그램이다.
 * 각 작업(job)은 지정된 block size 단위의 쓰기를 비동기 I/O로 수행하며,
 * numjobs, queue depth, block size, total size를 커맨드라인 인자로 설정할 수 있다.
 *
 * 컴파일 예: gcc -O2 -o ssd_write_bw ssd_write_bw.c -luring -lpthread
 */

#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <ctype.h>
#include <string.h>
#include <errno.h>
#include <fcntl.h>
#include <unistd.h>
#include <pthread.h>
#include <time.h>
#include <liburing.h>

/* 크기 문자열(예:"4k", "4m", "4g")를 size_t 바이트 값으로 변환하는 함수이다. */
size_t parse_size(const char *str) {
    char *end;
    long long num = strtoll(str, &end, 10);
    if (num < 0) {
        fprintf(stderr, "음수 크기는 허용되지 않는다.\n");
        exit(EXIT_FAILURE);
    }
    if (*end != '\0') {
        /* 단위 문자가 한 글자인지 확인한다. */
        if (end[1] != '\0') {
            fprintf(stderr, "잘못된 크기 형식: %s\n", str);
            exit(EXIT_FAILURE);
        }
        switch (tolower(*end)) {
            case 'k':
                num *= 1024LL;
                break;
            case 'm':
                num *= 1024LL * 1024LL;
                break;
            case 'g':
                num *= 1024LL * 1024LL * 1024LL;
                break;
            default:
                fprintf(stderr, "알 수 없는 크기 단위: %s\n", str);
                exit(EXIT_FAILURE);
        }
    }
    return (size_t)num;
}

/* 프로그램 사용법을 출력하는 함수이다. */
void usage(const char *progname) {
    fprintf(stderr,
            "Usage: %s [options]\n"
            "Options:\n"
            "  -f <file>       타겟 파일 이름 (기본: testfile.dat)\n"
            "  -j <numjobs>    동시 작업 수 (기본: 1)\n"
            "  -q <queue_depth> I/O 큐 깊이 (기본: 1)\n"
            "  -b <block_size> 블록 크기 (예: 4k, 4m; 기본: 4k)\n"
            "  -t <total_size> 총 쓰기 크기 (예: 1g; 기본: 1g)\n"
            "  -h              도움말 출력\n",
            progname);
}

/* 각 스레드가 사용할 컨텍스트 구조체이다. */
typedef struct {
    const char *filename;   /* 타겟 파일 이름 */
    off_t offset;           /* 파일 내 시작 오프셋 */
    size_t total_bytes;     /* 해당 작업이 수행할 총 바이트 수 */
    size_t block_size;      /* 블록 크기 */
    int queue_depth;        /* I/O 큐 깊이 */
} thread_context_t;

/* 각 스레드가 수행할 작업 함수이다.
 * 각 스레드는 지정된 범위 내에서 block_size 단위의 비동기 쓰기를 io_uring을 이용하여 제출하고,
 * 완료 이벤트를 기다린다.
 */
void *thread_worker(void *arg) {
    thread_context_t *ctx = (thread_context_t *)arg;

    /* O_DIRECT 플래그를 사용하여 페이지 캐시의 영향을 배제한다. */
    int fd = open(ctx->filename, O_WRONLY | O_DIRECT, 0644);
    if (fd < 0) {
        perror("open");
        pthread_exit((void *)1);
    }

    /* block_size 크기만큼 4096바이트 정렬된 버퍼를 할당한다. */
    void *buffer;
    int ret = posix_memalign(&buffer, 4096, ctx->block_size);
    if (ret != 0) {
        fprintf(stderr, "posix_memalign 실패: %s\n", strerror(ret));
        close(fd);
        pthread_exit((void *)1);
    }
    /* 버퍼를 임의의 패턴(0x55)으로 채운다. */
    memset(buffer, 0x55, ctx->block_size);

    /* io_uring의 I/O 컨텍스트를 초기화한다. */
    struct io_uring ring;
    ret = io_uring_queue_init(ctx->queue_depth, &ring, 0);
    if (ret < 0) {
        fprintf(stderr, "io_uring_queue_init 오류: %s\n", strerror(-ret));
        free(buffer);
        close(fd);
        pthread_exit((void *)1);
    }

    int total_ios = ctx->total_bytes / ctx->block_size;
    int submitted = 0;  /* 제출한 I/O 요청 수 */
    int pending = 0;    /* 미완료 I/O 요청 수 */

    /*
     * 제출과 완료를 슬라이딩 윈도우 방식으로 수행한다.
     * 제출 가능한 경우 SQ에 요청을 추가하고, 큐가 가득 찼거나 제출이 완료된 경우
     * 최소 1개의 완료 이벤트를 기다린다.
     */
    while (submitted < total_ios || pending > 0) {
        /* 제출 가능한 경우 I/O 요청을 제출한다. */
        while (submitted < total_ios && pending < ctx->queue_depth) {
            struct io_uring_sqe *sqe = io_uring_get_sqe(&ring);
            if (!sqe) {
                /* SQ가 가득 찼다면 루프를 빠져나간다. */
                break;
            }
            off_t io_offset = ctx->offset + submitted * ctx->block_size;
            io_uring_prep_write(sqe, fd, buffer, ctx->block_size, io_offset);
            /* 필요에 따라 user_data를 설정한다. 여기서는 제출 번호를 저장한다. */
            sqe->user_data = submitted;
            submitted++;
            pending++;
        }
        /* 제출한 I/O 요청을 커널에 전달한다. */
        ret = io_uring_submit(&ring);
        if (ret < 0) {
            fprintf(stderr, "io_uring_submit 오류: %s\n", strerror(-ret));
            break;
        }
        /* 미완료 I/O 요청 중 최소 1개의 완료 이벤트를 기다린다. */
        struct io_uring_cqe *cqe;
        ret = io_uring_wait_cqe(&ring, &cqe);
        if (ret < 0) {
            fprintf(stderr, "io_uring_wait_cqe 오류: %s\n", strerror(-ret));
            break;
        }
        if (cqe->res < 0) {
            fprintf(stderr, "I/O 오류: %s\n", strerror(-cqe->res));
            io_uring_cqe_seen(&ring, cqe);
            break;
        }
        /* 완료된 I/O 요청을 회수한다. */
        io_uring_cqe_seen(&ring, cqe);
        pending--;
    }

    io_uring_queue_exit(&ring);
    free(buffer);
    close(fd);
    pthread_exit(NULL);
}

int main(int argc, char *argv[]) {
    const char *filename = "/dev/nvme2n1";
    int numjobs = 4;
    int queue_depth = 16;
    size_t block_size = parse_size("4k");    /* 기본 블록 크기는 4k이다. */
    size_t total_size = parse_size("4g");      /* 기본 총 쓰기 크기는 4g이다. */

    int opt;
    while ((opt = getopt(argc, argv, "f:j:q:b:t:h")) != -1) {
        switch (opt) {
            case 'f':
                filename = optarg;
                break;
            case 'j':
                numjobs = atoi(optarg);
                if (numjobs <= 0)
                    numjobs = 1;
                break;
            case 'q':
                queue_depth = atoi(optarg);
                if (queue_depth <= 0)
                    queue_depth = 1;
                break;
            case 'b':
                block_size = parse_size(optarg);
                break;
            case 't':
                total_size = parse_size(optarg);
                break;
            case 'h':
            default:
                usage(argv[0]);
                exit(EXIT_FAILURE);
        }
    }

    /* 총 쓰기 크기는 반드시 block size의 배수여야 한다. */
    if (total_size % block_size != 0) {
        fprintf(stderr, "총 쓰기 크기는 블록 크기의 배수여야 한다.\n");
        exit(EXIT_FAILURE);
    }

    /*
     * 각 스레드가 처리할 바이트 수를 계산한다.
     * 전체 total_size는 block_size의 배수이다.
     * 각 스레드에는 전체 블록 수(nblocks)를 numjobs로 나눈 몫에 해당하는 바이트 수를 할당하고,
     * 마지막 스레드는 나머지를 포함한다.
     */
    size_t nblocks = total_size / block_size;
    size_t blocks_per_job = nblocks / numjobs;
    size_t base_job_size = blocks_per_job * block_size;
    size_t last_job_size = total_size - base_job_size * (numjobs - 1);

    pthread_t *threads = malloc(sizeof(pthread_t) * numjobs);
    thread_context_t *contexts = malloc(sizeof(thread_context_t) * numjobs);
    if (!threads || !contexts) {
        perror("스레드/컨텍스트 메모리 할당 실패");
        exit(EXIT_FAILURE);
    }

    /* 전체 수행시간을 측정하기 위해 시작 시간을 기록한다. */
    struct timespec start, end;
    clock_gettime(CLOCK_MONOTONIC, &start);

    for (int i = 0; i < numjobs; i++) {
        contexts[i].filename = filename;
        contexts[i].offset = i * base_job_size;
        if (i == numjobs - 1)
            contexts[i].total_bytes = last_job_size;
        else
            contexts[i].total_bytes = base_job_size;
        contexts[i].block_size = block_size;
        contexts[i].queue_depth = queue_depth;
        if (pthread_create(&threads[i], NULL, thread_worker, &contexts[i]) != 0) {
            perror("pthread_create");
            exit(EXIT_FAILURE);
        }
    }

    for (int i = 0; i < numjobs; i++) {
        pthread_join(threads[i], NULL);
    }

    clock_gettime(CLOCK_MONOTONIC, &end);
    double elapsed = (end.tv_sec - start.tv_sec) + (end.tv_nsec - start.tv_nsec) / 1e9;
    double mb_written = total_size / (1024.0 * 1024.0);
    double bandwidth = mb_written / elapsed;

    printf("총 %.2f MB를 %.2f 초 동안 기록하였으며, 대역폭은 %.2f MB/s이다.\n",
           mb_written, elapsed, bandwidth);

    free(threads);
    free(contexts);
    return 0;
}
