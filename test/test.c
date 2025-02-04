/*
 * ssd_write_bw.c
 *
 * 이 프로그램은 libaio와 io_uring을 선택적으로 사용하여 SSD write bandwidth를 측정하는 프로그램이다.
 * 각 작업(job)은 지정된 block size 단위의 쓰기를 비동기 I/O로 수행하며,
 * numjobs, queue depth, block size, total size, I/O 방식(libaio 또는 io_uring)을 커맨드라인 인자로 설정할 수 있다.
 *
 * 컴파일 예: gcc -O2 -o ssd_write_bw ssd_write_bw.c -laio -luring -lpthread
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
#include <libaio.h>
#include <pthread.h>
#include <time.h>
#include <liburing.h>

/* I/O 방식 열거형: 기본은 libaio, io_uring을 선택할 수 있다. */
typedef enum {
    METHOD_LIBAIO,
    METHOD_IOURING
} io_method_t;

/* 각 스레드가 사용할 컨텍스트 구조체이다.
 * 각 스레드는 main에서 할당받은 파일의 특정 영역에 대해 쓰기를 수행한다.
 */
typedef struct {
    const char *filename;   /* 타겟 파일 이름 */
    off_t offset;           /* 스레드가 시작할 파일 내 오프셋 */
    size_t total_bytes;     /* 해당 스레드가 수행할 총 바이트 수 */
    size_t block_size;      /* 블록 크기 */
    int queue_depth;        /* I/O 큐 깊이 */
    io_method_t method;     /* I/O 방식: METHOD_LIBAIO 또는 METHOD_IOURING */
} thread_context_t;

typedef struct {
    int *data;
    atomic_int top;  // 스택의 top 인덱스를 원자적으로 관리한다.
} Stack;

static Stack stack;  // 전역 스택 변수이다.

void init_stack() {
    FILE *fp = fopen("testset.txt", "r");
    if (fp == NULL) {
        fprintf(stderr, "파일 열기에 실패하였다.\n");
        exit(EXIT_FAILURE);
    }
    
    // 초기 메모리 할당 크기를 10으로 설정하였다.
    int capacity = 256;
    int count = 0;
    int *list = (int *)malloc(capacity * sizeof(int));
    if (list == NULL) {
        fprintf(stderr, "메모리 할당에 실패하였다.\n");
        fclose(fp);
        exit(EXIT_FAILURE);
    }
    
    // 파일에서 정수를 하나씩 읽어서 list에 저장한다.
    while (fscanf(fp, "%d", &list[count]) == 1) {
        count++;
        // 배열의 공간이 부족하면 메모리 크기를 두 배로 늘린다.
        if (count == capacity) {
            capacity *= 2;
            int *temp = (int *)realloc(list, capacity * sizeof(int));
            if (temp == NULL) {
                fprintf(stderr, "메모리 재할당에 실패하였다.\n");
                free(list);
                fclose(fp);
                exit(EXIT_FAILURE);
            }
            list = temp;
        }
    }
    
    fclose(fp);

    stack.data = list;
    atomic_init(&stack.top, count);
}

// pop 함수는 스택에서 원자적으로 하나의 요소를 제거한다.
// 요소가 남아있으면 *value에 값을 저장하고 1을 반환하며, 없으면 0을 반환한다.
int pop() {
    // atomic_fetch_sub는 현재 top 값을 반환한 후 1을 감소시킨다.
    int old_top = atomic_fetch_sub(&stack.top, 1);
    if (old_top <= 0) {
        // 스택에 남은 요소가 없으므로, 감소한 값을 복구한다.
        atomic_fetch_add(&stack.top, 1);
        return -1;  // pop 실패
    }

    return stack.data[old_top - 1];
}

/* 크기 문자열(예: "4k", "4m", "4g")를 size_t 바이트 값으로 변환하는 함수이다. */
size_t parse_size(const char *str) {
    char *end;
    long long num = strtoll(str, &end, 10);
    if (num < 0) {
        fprintf(stderr, "음수 크기는 허용되지 않는다.\n");
        exit(EXIT_FAILURE);
    }
    if (*end != '\0') {
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
            "  -f <file>       타겟 파일 이름 (기본: /dev/nvme2n1)\n"
            "  -j <numjobs>    동시 작업 수 (기본: 4)\n"
            "  -q <queue_depth> I/O 큐 깊이 (기본: 16)\n"
            "  -b <block_size> 블록 크기 (예: 4k, 4m; 기본: 4k)\n"
            "  -t <total_size> 총 쓰기 크기 (예: 4g; 기본: 4g)\n"
            "  -m <method>     I/O 방식 (libaio 또는 io_uring, 기본: libaio)\n"
            "  -h              도움말 출력\n",
            progname);
}

/* 각 스레드가 수행할 작업 함수이다.
 * 스레드는 자신에게 할당된 파일 영역(ctx->offset부터 total_bytes만큼)에 대해
 * block_size 단위의 비동기 쓰기를 제출하고 완료 이벤트를 기다린다.
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

    int total_ios = ctx->total_bytes / ctx->block_size;

    if (ctx->method == METHOD_LIBAIO) {
        /* --- libaio 방식 --- */
        io_context_t io_ctx = 0;
        ret = io_setup(ctx->queue_depth, &io_ctx);
        if (ret < 0) {
            fprintf(stderr, "io_setup 오류: %s\n", strerror(-ret));
            free(buffer);
            close(fd);
            pthread_exit((void *)1);
        }

        struct io_event *events = malloc(sizeof(struct io_event) * ctx->queue_depth);
        if (!events) {
            perror("malloc events");
            io_destroy(io_ctx);
            free(buffer);
            close(fd);
            pthread_exit((void *)1);
        }

        int submitted = 0;
        int pending = 0;

        /* 제출과 완료를 슬라이딩 윈도우 방식으로 수행한다. */
        while (submitted < total_ios) {
            if (pending < ctx->queue_depth) {
                off_t io_offset = pop() * ctx->block_size;
                struct iocb *iocb_ptr = malloc(sizeof(struct iocb));
                if (!iocb_ptr) {
                    perror("malloc iocb");
                    break;
                }
                io_prep_pwrite(iocb_ptr, fd, buffer, ctx->block_size, io_offset);
                /* 완료 시 해당 iocb를 회수할 수 있도록 data 필드에 자기자신의 포인터를 저장한다. */
                iocb_ptr->data = iocb_ptr;
                ret = io_submit(io_ctx, 1, &iocb_ptr);
                if (ret != 1) {
                    fprintf(stderr, "io_submit 오류: %s\n", strerror(-ret));
                    free(iocb_ptr);
                    break;
                }
                submitted++;
                pending++;
            } else {
                int got = io_getevents(io_ctx, 1, pending, events, NULL);
                if (got < 0) {
                    fprintf(stderr, "io_getevents 오류: %s\n", strerror(-got));
                    break;
                }
                for (int i = 0; i < got; i++) {
                    free((void *)events[i].obj);
                }
                pending -= got;
            }
        }
        /* 남은 미완료 I/O 요청들을 모두 완료시킨다. */
        while (pending > 0) {
            int got = io_getevents(io_ctx, 1, pending, events, NULL);
            if (got < 0) {
                fprintf(stderr, "io_getevents 오류: %s\n", strerror(-got));
                break;
            }
            for (int i = 0; i < got; i++) {
                free((void *)events[i].obj);
            }
            pending -= got;
        }
        io_destroy(io_ctx);
        free(events);
    } else if (ctx->method == METHOD_IOURING) {
        /* --- io_uring 방식 --- */
        struct io_uring ring;
        ret = io_uring_queue_init(ctx->queue_depth, &ring, 0);
        if (ret < 0) {
            fprintf(stderr, "io_uring_queue_init 오류: %s\n", strerror(-ret));
            free(buffer);
            close(fd);
            pthread_exit((void *)1);
        }

        int submitted = 0;
        int pending = 0;

        /* 제출 가능한 경우 SQ에 요청을 추가하고, 완료 이벤트를 기다린다. */
        while (submitted < total_ios || pending > 0) {
            while (submitted < total_ios && pending < ctx->queue_depth) {
                struct io_uring_sqe *sqe = io_uring_get_sqe(&ring);
                if (!sqe) {
                    /* SQ가 가득 찼다면 루프를 종료한다. */
                    break;
                }
                off_t io_offset = ctx->offset + submitted * ctx->block_size;
                io_uring_prep_write(sqe, fd, buffer, ctx->block_size, io_offset);
                sqe->user_data = submitted;
                submitted++;
                pending++;
            }
            ret = io_uring_submit(&ring);
            if (ret < 0) {
                fprintf(stderr, "io_uring_submit 오류: %s\n", strerror(-ret));
                break;
            }
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
            io_uring_cqe_seen(&ring, cqe);
            pending--;
        }
        io_uring_queue_exit(&ring);
    }

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
    io_method_t method = METHOD_LIBAIO;        /* 기본 I/O 방식은 libaio이다. */
    
    init_stack();

    int opt;
    while ((opt = getopt(argc, argv, "f:j:q:b:t:m:h")) != -1) {
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
            case 'm':
                if (strcasecmp(optarg, "libaio") == 0)
                    method = METHOD_LIBAIO;
                else if (strcasecmp(optarg, "io_uring") == 0)
                    method = METHOD_IOURING;
                else {
                    fprintf(stderr, "알 수 없는 I/O 방식: %s\n", optarg);
                    usage(argv[0]);
                    exit(EXIT_FAILURE);
                }
                break;
            case 'h':
            default:
                usage(argv[0]);
                exit(EXIT_FAILURE);
        }
    }

    /* 총 쓰기 크기는 반드시 블록 크기의 배수여야 한다. */
    if (total_size % block_size != 0) {
        fprintf(stderr, "총 쓰기 크기는 블록 크기의 배수여야 한다.\n");
        exit(EXIT_FAILURE);
    }

    /* 각 스레드가 처리할 바이트 수를 계산한다.
     * 전체 total_size는 block_size의 배수이며,
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
        contexts[i].method = method;
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
