program While;
    var i: integer;
    var f: integer;
begin
    i := 1;
    f := 1;
    while i <= 5 do
        begin
            f := f * i;
            i := i + 1
        end;
    if f = 120 then
        halt(42)
end.
