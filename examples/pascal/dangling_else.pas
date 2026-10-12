program Dangle;
    var x: integer;
begin
    x := 1;
    if x = 1 then
        if x = 2 then
            halt(7)
        else
            halt(8);
    halt(x + 42)
end.
