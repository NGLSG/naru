extern int shared_counter;
int twice(int);
int main(void) { return twice(shared_counter); }
