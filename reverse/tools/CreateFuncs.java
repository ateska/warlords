import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import java.nio.file.*;
public class CreateFuncs extends GhidraScript {
  public void run() throws Exception {
    int n=0;
    for (String line : Files.readAllLines(Paths.get("funcs.txt"))) {
      line=line.trim(); if (line.isEmpty()) continue;
      Address a = currentProgram.getAddressFactory().getAddress(line);
      if (a==null) continue;
      if (getFunctionAt(a)==null) {
        disassemble(a);
        if (createFunction(a, null)!=null) n++;
      }
    }
    println("created " + n);
  }
}
