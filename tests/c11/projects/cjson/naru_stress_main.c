#include "cJSON.h"
int main(void) {
    cJSON *root = cJSON_Parse("{\"answer\":42,\"text\":\"\\u6d8c\\u73b0\"}");
    if (!root) return 1;
    cJSON *answer = cJSON_GetObjectItemCaseSensitive(root, "answer");
    int okay = cJSON_IsNumber(answer) && answer->valueint == 42;
    cJSON_Delete(root);
    return okay ? 42 : 1;
}
