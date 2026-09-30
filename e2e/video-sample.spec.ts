import { test, expect } from '@playwright/test';

test('real sample video plays, seeks with tracks and downloads the annotated clip', async ({page})=>{
  const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('/');
  await page.locator('nav').getByRole('button',{name:'Тестовое видео',exact:true}).click();
  const video=page.getByLabel('Видео с рабочими');
  await expect.poll(()=>video.evaluate((v:HTMLVideoElement)=>v.readyState),{timeout:15000}).toBeGreaterThanOrEqual(2);
  await video.evaluate((v:HTMLVideoElement)=>v.play());
  await expect.poll(()=>video.evaluate((v:HTMLVideoElement)=>v.currentTime)).toBeGreaterThan(.2);
  await video.evaluate((v:HTMLVideoElement)=>{v.pause();return new Promise<void>(resolve=>{v.addEventListener('seeked',()=>resolve(),{once:true});v.currentTime=3;});});
  await expect(page.locator('.sample-track')).toHaveCount(2);
  await expect(page.getByText('Трек #1',{exact:true})).toBeVisible();
  await expect(page.getByText('Трек #2',{exact:true})).toBeVisible();
  const canvas=page.getByLabel('Рамки и идентификаторы треков');
  expect(await canvas.evaluate((c:HTMLCanvasElement)=>c.getContext('2d')!.getImageData(0,0,c.width,c.height).data.some((value,index)=>index%4===3&&value>0))).toBe(true);
  await page.getByRole('button',{name:'Разметка видео',exact:true}).click();
  await expect(canvas).toBeHidden();
  await page.getByRole('button',{name:'Разметка видео',exact:true}).click();
  await expect(canvas).toBeVisible();
  const download=page.waitForEvent('download');
  await page.getByRole('link',{name:'Скачать видео с разметкой'}).click();
  expect((await download).suggestedFilename()).toBe('HSE-workers-analysis.mp4');
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  expect(errors).toEqual([]);
});

test('missing video protocol shows an error without generated tracks',async({page})=>{
  await page.route('**/samples/workers-analysis.json',route=>route.fulfill({status:404,body:'missing'}));
  await page.goto('/');
  await page.locator('nav').getByRole('button',{name:'Тестовое видео',exact:true}).click();
  await expect(page.getByRole('alert')).toContainText('Файлы анализа не найдены');
  await expect(page.locator('.sample-track')).toHaveCount(0);
});
