"""
This snippet demonstrates the possibility for multiple clients
(in this case, threads on the same machine) to cause 
out-of-order Object IDs in a MongoDB collection.

The code simply creates a number of threads, which read from a
list of numbers 1:N in a shared queue, and insert that number into
MongoDB. In the results, one can see how mis-ordered Object IDs
match mis-ordered numbers.

"""
import sys, pymongo, Queue, threading, time

# Set these to your preferred DB and collection name
DB = 'test'
COLL = 'skew'

# Change this to True to see
# that serializing the threads makes the
# ObjectIDs become ordered again.
g_serialize = False 
if g_serialize:
    g_insert_lock = threading.Lock()

def insert(coll, q):
    while 1:
        try:
            if g_serialize:
                with g_insert_lock:
                    coll.insert(q.get_nowait())
            else:
                coll.insert(q.get_nowait())
        except Queue.Empty:
            break
    
def fill_queue(q, num_items):
    for i in xrange(num_items):
        q.put({'i': i+1})
    return q
    
def create_threads(num_threads, db_name, coll_name, q):
    coll = pymongo.MongoClient()[db_name][coll_name]
    coll.remove()
    threads = []
    for i in range(num_threads):
        coll = pymongo.MongoClient()[db_name][coll_name]
        threads.append(threading.Thread(target=insert, args=(coll, q)))
    return threads

def main():
    nitems, nthreads = 100, 10
    q = fill_queue(Queue.Queue(), nitems)
    threads = create_threads(nthreads, DB, COLL, q)
    print("Start")
    t0 = time.time()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    t1 = time.time()
    print("Stop")
    print("Start time = {:f}".format(t0))
    print("End time = {:f}".format(t1))
    coll = pymongo.MongoClient()[DB][COLL]
    prev = 0
    for rec in coll.find():
        ooo_flag = ('', '**')[rec['i'] != prev + 1]
        print("{:3d} {:16s} {}".format(rec['i'], rec['_id'], ooo_flag))
        prev = rec['i']
    

if __name__ == '__main__':
    main()
