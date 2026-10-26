"""Production-function regression tests; run with python3 test_host.py."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[4]

def function(file, signature):
    source = (ROOT / 'subsys/settings/src' / file).read_text()
    start = source.index(signature + '\n{')
    return source[start:source.index('\n}', start) + 2]

prefix = r'''
#include <assert.h>
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include <sys/types.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>
#define MIN(a,b) ((a)<(b)?(a):(b))
#define SETTINGS_MAX_NAME_LEN 64
#define SETTINGS_EXTRA_LEN 8
#define CONFIG_SETTINGS_NVS_NAME_CACHE_SIZE 4
#define ARRAY_SIZE(a) (sizeof(a)/sizeof((a)[0]))
#define SETTINGS_NVS_CACHE_OVFL(cf) ((cf)->cache_total > ARRAY_SIZE((cf)->cache))
#define NVS_NAMECNT_ID 1
#define NVS_NAME_ID_OFFSET 100
#define LOG_DBG(...)
#define LOG_ERR(...)
#define CONTAINER_OF(ptr,type,member) ((type *)((char *)(ptr)-offsetof(type,member)))
struct nvs_fs { void *flash_device; };
struct settings_load_arg { const char *subtree; int (*cb)(const char *,size_t,ssize_t (*)(void *,void *,size_t),void *,void *); void *param; };
struct settings_store;
struct settings_store_itf { int (*csi_load)(struct settings_store *, const struct settings_load_arg *); };
struct settings_store { const struct settings_store_itf *cs_itf; };
struct settings_nvs { struct settings_store cf_store; struct nvs_fs cf_nvs; void *flash_dev; uint16_t last_name_id; bool loaded; unsigned cache_total,cache_next; struct { uint16_t name_hash,name_id; } cache[4]; };
struct settings_nvs_read_fn_arg { struct nvs_fs *fs; uint16_t id; size_t len; int error; };
static unsigned char records[202][80];
static int read_count[202], fault_on_call, sizes[202], fault_id=-1, fault=-EIO, deletes,writes,commits,locks,handler_error,mount_error,write_error,swallow_read;
static ssize_t nvs_read(struct nvs_fs *fs,uint16_t id,void *buf,size_t len) {
 (void)fs; assert(id<202); read_count[id]++; if(id==fault_id && (!fault_on_call || read_count[id]==fault_on_call))return fault;
 if(sizes[id]<0)return sizes[id];
 memcpy(buf,records[id],len<(size_t)sizes[id]?len:(size_t)sizes[id]);return sizes[id];
}
static int nvs_delete(struct nvs_fs *fs,uint16_t id) { (void)fs;deletes++;sizes[id]=-ENOENT;return 0; }
static int nvs_write(struct nvs_fs *fs,uint16_t id,const void *buf,size_t len) { (void)fs;writes++;if(write_error)return write_error;memcpy(records[id],buf,len);sizes[id]=len;return len; }
static int nvs_mount(struct nvs_fs *fs) { (void)fs;return mount_error; }
#if CONFIG_SETTINGS_NVS_NAME_CACHE
static uint16_t crc16_ccitt(uint16_t seed,const char *buf,size_t len) { while(len--)seed=seed*31+*buf++;return seed; }
#endif
static void settings_lock_take(void) {locks++;}
static void settings_lock_release(void) {locks--;}
static int settings_commit_subtree(const char *s) {(void)s;commits++;return 0;}
static struct settings_store *settings_load_srcs;
#define SYS_SLIST_FOR_EACH_CONTAINER(list,cs,member) for(cs=*(list);cs!=NULL;cs=NULL)
typedef ssize_t (*settings_read_cb)(void *,void *,size_t);
static int settings_name_steq(const char *name,const char *sub,const char **next) {size_t n=strlen(sub);if(strncmp(name,sub,n)||(name[n] && name[n]!='/'))return 0;if(next)*next=name[n]?name+n+1:NULL;return 1;}
struct settings_handler_static {int (*h_set)(const char *,size_t,settings_read_cb,void *);};
static int set(const char *name,size_t len,settings_read_cb cb,void *arg) {char b[80];(void)name;int rc=cb(arg,b,len);return swallow_read?0:(rc<0?rc:handler_error);}
static struct settings_handler_static handler={.h_set=set};
static struct settings_handler_static *settings_parse_and_lookup(const char *name,const char **next) {if(!strncmp(name,"unknown/",8))return NULL;*next=name;return &handler;}
'''
suffix = r'''
static void reset(void) {for(int i=0;i<202;i++)sizes[i]=-ENOENT;memset(read_count,0,sizeof(read_count));fault_on_call=0;fault_id=-1;fault=-EIO;writes=deletes=commits=locks=handler_error=mount_error=write_error=swallow_read=0;}
static void pair(int id,const char *name) {sizes[id]=strlen(name);memcpy(records[id],name,sizes[id]);sizes[id+100]=4;memcpy(records[id+100],"data",4);}
static void unchanged(struct settings_nvs *cf,int expected) {assert(writes==0 && deletes==0 && cf->last_name_id==expected);}
int main(void) {
 struct settings_load_arg arg={0};
 struct settings_nvs cf;
 for(int id=2;id<=103;id++) {
  if(id>3 && id<102)continue;
  reset();cf=(struct settings_nvs){.last_name_id=3};pair(2,"bt/keys");pair(3,"pedal/bank/0");fault_id=id;
  assert(settings_nvs_load(&cf.cf_store,&arg)==-EIO);unchanged(&cf,3);
 }
 reset();cf=(struct settings_nvs){.last_name_id=3};pair(2,"bt/id");fault_id=102;
 assert(settings_nvs_load(&cf.cf_store,&arg)==-EIO);unchanged(&cf,3);
 for(int id=2;id<=102;id+=100) {
  reset();cf=(struct settings_nvs){.last_name_id=2};pair(2,"bt/irk");sizes[id]=0;
  assert(settings_nvs_load(&cf.cf_store,&arg)==-EINVAL);unchanged(&cf,2);
 }
 reset();cf=(struct settings_nvs){.last_name_id=3};pair(2,"bt/id");sizes[103]=4;
 assert(settings_nvs_load(&cf.cf_store,&arg)==0);unchanged(&cf,3);
 reset();cf=(struct settings_nvs){.last_name_id=2};pair(2,"bt/id");handler_error=-EIO;
 assert(settings_nvs_load(&cf.cf_store,&arg)==-EIO);unchanged(&cf,2);
 handler_error=-ENOENT;assert(settings_nvs_load(&cf.cf_store,&arg)==0);
 for(int injected=-EIO;injected<=2;injected+=7) {
  reset();cf=(struct settings_nvs){.last_name_id=2};pair(2,"bt/id");fault_id=102;fault_on_call=2;fault=injected;swallow_read=1;
  assert(settings_nvs_load(&cf.cf_store,&arg)==-EIO);unchanged(&cf,2);
 }
 reset();cf=(struct settings_nvs){.last_name_id=2};pair(2,"bt/id");sizes[2]=73;
 assert(settings_nvs_load(&cf.cf_store,&arg)==-EINVAL);unchanged(&cf,2);
 reset();cf=(struct settings_nvs){.last_name_id=2};pair(2,"bt/id");records[2][2]=0;
 assert(settings_nvs_load(&cf.cf_store,&arg)==-EINVAL);unchanged(&cf,2);
 reset();cf=(struct settings_nvs){.flash_dev=(void *)1,.last_name_id=77};fault_id=1;
 assert(settings_nvs_backend_init(&cf)==-EIO);unchanged(&cf,77);
 fault_id=-1;assert(settings_nvs_backend_init(&cf)==0);assert(cf.last_name_id==1);
 for(int len=0;len<=3;len++) {if(len==2)continue;sizes[1]=len;cf.last_name_id=77;assert(settings_nvs_backend_init(&cf)==-EINVAL);unchanged(&cf,77);}
 for(int value=0;value<=101;value+=101) {uint16_t v=value;sizes[1]=2;memcpy(records[1],&v,2);assert(settings_nvs_backend_init(&cf)==-EINVAL);}
 reset();cf=(struct settings_nvs){.last_name_id=2};pair(2,"pedal/bank/0");fault_id=2;
 assert(settings_nvs_save(&cf.cf_store,"pedal/bank/0","new",3)==-EIO);unchanged(&cf,2);
#if CONFIG_SETTINGS_NVS_NAME_CACHE
 cf.cache[0].name_hash=crc16_ccitt(0xffff,"pedal/bank/0",12);cf.cache[0].name_id=2;
 assert(settings_nvs_save(&cf.cf_store,"pedal/bank/0","new",3)==-EIO);unchanged(&cf,2);
#endif
 reset();cf=(struct settings_nvs){.last_name_id=1};
 assert(settings_nvs_save(&cf.cf_store,"pedal/bank/0","old",3)==0);assert(cf.last_name_id==2);
 assert(settings_nvs_save(&cf.cf_store,"bt/id","id",2)==0);assert(cf.last_name_id==3);
 unsigned char snapshot[sizeof(records)];memcpy(snapshot,records,sizeof(records));
 writes=0;assert(settings_nvs_load(&cf.cf_store,&arg)==0);unchanged(&cf,3);assert(!memcmp(snapshot,records,sizeof(records)));
 assert(settings_nvs_save(&cf.cf_store,"pedal/bank/0","new",3)==0);assert(cf.last_name_id==3);
 assert(settings_nvs_save(&cf.cf_store,"pedal/bank/0",NULL,0)==0);assert(sizes[2]==-ENOENT && sizes[102]==-ENOENT);assert(sizes[3]==5);
 write_error=-ENOSPC;assert(settings_nvs_save(&cf.cf_store,"bt/id","id",2)==-ENOSPC);
 const struct settings_store_itf itf={.csi_load=settings_nvs_load};cf.cf_store.cs_itf=&itf;settings_load_srcs=&cf.cf_store;
 fault_id=3;assert(settings_load_subtree(NULL)==-EIO);assert(locks==0 && commits==0);
 assert(settings_load_subtree_direct(NULL,NULL,NULL)==-EIO);assert(locks==0 && commits==0);
 puts("PASS: production Settings/NVS preservation matrix");
}
'''
functions = [function('settings.c','int settings_call_set_handler(const char *name,\n\t\t\t      size_t len,\n\t\t\t      settings_read_cb read_cb,\n\t\t\t      void *read_cb_arg,\n\t\t\t      const struct settings_load_arg *load_arg)'), function('settings_nvs.c','static ssize_t settings_nvs_read_fn(void *back_end, void *data, size_t len)')]
cache = [function('settings_nvs.c','static void settings_nvs_cache_add(struct settings_nvs *cf, const char *name,\n\t\t\t\t   uint16_t name_id)'),function('settings_nvs.c','static int settings_nvs_cache_match(struct settings_nvs *cf, const char *name,\n\t\t\t\t\t char *rdname, size_t len)')]
rest = [function('settings_nvs.c',s) for s in ['static int settings_nvs_load(struct settings_store *cs,\n\t\t\t     const struct settings_load_arg *arg)','static int settings_nvs_save(struct settings_store *cs, const char *name,\n\t\t\t     const char *value, size_t val_len)','int settings_nvs_backend_init(struct settings_nvs *cf)']]
rest += [function('settings_store.c','int settings_load_subtree(const char *subtree)'),function('settings_store.c','int settings_load_subtree_direct(\n\tconst char             *subtree,\n\tsettings_load_direct_cb cb,\n\tvoid                   *param)')]
prefix += '\ntypedef int (*settings_load_direct_cb)(const char *,size_t,settings_read_cb,void *,void *);\n'
with tempfile.TemporaryDirectory() as tmp:
    for enabled in (0,1):
        source=Path(tmp)/'matrix.c';binary=Path(tmp)/'matrix'
        source.write_text(f'#define CONFIG_SETTINGS_NVS_NAME_CACHE {enabled}\n'+prefix+'\n'.join(functions+(cache if enabled else [])+rest)+suffix)
        subprocess.run(['cc','-std=c11','-Wall','-Wextra',str(source),'-o',str(binary)],check=True)
        subprocess.run([str(binary)],check=True)
