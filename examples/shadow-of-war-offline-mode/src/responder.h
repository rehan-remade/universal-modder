#pragma once
#include <stddef.h>
#include <wchar.h>

typedef struct { int status; unsigned char *body; size_t len; } Response;

void responder_init(const wchar_t *dataFile, int garrisonSize);
/* Builds the local answer to one Hydra request. Never touches the network. */
void respond(const wchar_t *verb, const wchar_t *path, const unsigned char *req, size_t reqLen, Response *out);
void resp_free(Response *r);
void logw(const wchar_t *fmt, ...);
